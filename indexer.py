from __future__ import annotations

import time
import logging
import urllib.parse
from dataclasses import dataclass

import protocol
from browser import GooglePhotosBrowser
from database import Database
from models import Album
from parser import GooglePhotosParser

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndexResult:
    album: Album
    media_count: int
    elapsed_seconds: float


class GooglePhotosIndexer:
    def __init__(self, database: Database | None = None) -> None:
        self.db = database or Database()

    async def index(self, url: str) -> IndexResult:
        self.db.create()

        parser = GooglePhotosParser()
        start_time = time.monotonic()

        parsed_url = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed_url.query)
        url_share_key = qs.get("key", [None])[0]

        # CHANGED: headless=False to force the browser to open visibly
        async with GooglePhotosBrowser(headless=False) as browser:
            await browser.navigate(url)
            
            try:
                rpc_id, payload = await browser.wait_for_rpc(["frGlJf", "snAcKc"])
            except TimeoutError as exc:
                raise TimeoutError(
                    f"No initial album payload received while indexing {url}"
                ) from exc

            album = parser.parse_album_metadata(rpc_id, payload)
            
            if not album.share_key and url_share_key:
                album.share_key = url_share_key

            media = parser.parse_album_listing(rpc_id, payload, album.id)

            self.db.save_album(album)
            self.db.save_many(media)

            if album.share_key:
                logger.info(f"Fetching metadata for {len(media)} items in batches...")
                media_ids = [m.media_id for m in media]
                chunk_size = 50
                
                with open("raw_fDcn4b_responses.txt", "w", encoding="utf-8") as f:
                    f.write(f"--- fDcn4b Raw Responses for Album: {album.id} ---\n\n")

                for i in range(0, len(media_ids), chunk_size):
                    batch_num = i // chunk_size
                    chunk = media_ids[i:i + chunk_size]
                    f_req = protocol.build_fDcn4b_batch(chunk, album.share_key)
                    
                    try:
                        raw_response = await browser.fetch_batchexecute("fDcn4b", f_req)
                        
                        with open("raw_fDcn4b_responses.txt", "a", encoding="utf-8") as f:
                            f.write(f"--- Batch {batch_num} ---\n")
                            f.write(raw_response + "\n\n")

                        decoded = protocol.decode_wrbs(raw_response)
                        
                        updated_count = 0
                        for resp_rpc_id, resp_payload in decoded:
                            if resp_rpc_id == "fDcn4b":
                                metadata = parser.parse_media_metadata(resp_payload)
                                self.db.update_metadata(metadata["media_id"], metadata)
                                updated_count += 1
                        
                        if updated_count > 0:
                            logger.info(f"Batch {batch_num}: Successfully parsed and updated {updated_count} items.")
                        else:
                            logger.warning(f"Batch {batch_num}: No valid fDcn4b items parsed. Check raw_fDcn4b_responses.txt.")
                                
                    except Exception as e:
                        logger.error(f"Failed to fetch or process metadata batch {batch_num}: {e}")

        return IndexResult(
            album=album,
            media_count=len(media),
            elapsed_seconds=time.monotonic() - start_time,
        )