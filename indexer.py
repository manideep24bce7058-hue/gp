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

            logger.info(f"Fetching metadata for {len(media)} items in batches concurrently...")
            media_ids = [m.media_id for m in media]
            chunk_size = 50
            
            with open("raw_fDcn4b_responses.txt", "w", encoding="utf-8") as f:
                f.write(f"--- fDcn4b Raw Responses for Album: {album.id} ---\n\n")

            import asyncio
            
            # Limit to 3 concurrent network requests at a time to prevent burst throttling
            sem = asyncio.Semaphore(3)
            
            async def process_batch(batch_num: int, chunk: list[str]) -> None:
                async with sem:
                    f_req = protocol.build_fDcn4b_batch(chunk, album.share_key or "")
                    
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            # Add a tiny stagger based on batch number
                            if attempt == 0:
                                await asyncio.sleep(batch_num * 0.2)
                                
                            raw_response = await browser.fetch_batchexecute("fDcn4b", f_req)
                            
                            with open("raw_fDcn4b_responses.txt", "a", encoding="utf-8") as f:
                                f.write(f"--- Batch {batch_num} ---\n")
                                f.write(raw_response + "\n\n")

                            decoded = protocol.decode_wrbs(raw_response)
                            
                            batch_updates = []
                            for resp_rpc_id, resp_payload in decoded:
                                if resp_rpc_id == "fDcn4b":
                                    metadata = parser.parse_media_metadata(resp_payload)
                                    batch_updates.append(metadata)
                            
                            if not batch_updates:
                                # Force a retry if Google returned an empty payload
                                raise Exception("Google returned 200 OK but stripped the data (Rate Limit).")

                            # Trigger the single transaction cloud DB write
                            self.db.update_metadata_batch(batch_updates)
                            logger.info(f"Batch {batch_num}: Successfully parsed and updated {len(batch_updates)} items.")
                            break # Success, exit retry loop
                            
                        except Exception as e:
                            logger.warning(f"Batch {batch_num} failed (Attempt {attempt + 1}/{max_retries}): {e}")
                            if attempt == max_retries - 1:
                                logger.error(f"Max retries reached. Batch {batch_num} failed completely.")
                            
                            # Exponential backoff: 2s, 4s, 8s
                            await asyncio.sleep(2 ** (attempt + 1))

            # Build and execute all tasks
            tasks = []
            for i in range(0, len(media_ids), chunk_size):
                batch_num = i // chunk_size
                chunk = media_ids[i:i + chunk_size]
                tasks.append(process_batch(batch_num, chunk))
                
            if tasks:
                await asyncio.gather(*tasks)

        return IndexResult(
            album=album,
            media_count=len(media),
            elapsed_seconds=time.monotonic() - start_time,
        )
    