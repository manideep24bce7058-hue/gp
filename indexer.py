from __future__ import annotations

import time
import logging
import urllib.parse
import asyncio
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
            try:
                await browser.page.goto("https://photos.google.com/robots.txt", wait_until="domcontentloaded")
                await browser.page.evaluate("""
                    navigator.serviceWorker.getRegistrations().then(registrations => {
                        for (let r of registrations) { r.unregister(); }
                    });
                """)
            except Exception as e:
                logger.debug(f"Could not clear service workers: {e}")

            album = None
            media = None
            valid_rpc_id = None
            
            for attempt in range(3):
                await browser.navigate(url)
                
                # Clear the queue from previous attempts to prevent stale data
                while not browser._all_rpcs_queue.empty():
                    browser._all_rpcs_queue.get_nowait()
                    
                start_wait = time.monotonic()
                success = False
                
                # Fast Consume Loop: Pop items directly off the queue as they arrive
                while time.monotonic() - start_wait < 15.0:
                    try:
                        rpc_id, payload = await asyncio.wait_for(browser._all_rpcs_queue.get(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue
                        
                    if rpc_id not in ("snAcKc", "frGlJf"):
                        continue
                        
                    try:
                        # Attempt to parse the payload
                        temp_album = parser.parse_album_metadata(rpc_id, payload)
                        temp_media = parser.parse_album_listing(rpc_id, payload, temp_album.id)
                        
                        if temp_media:
                            album = temp_album
                            media = temp_media
                            valid_rpc_id = rpc_id
                            success = True
                            break
                    except Exception:
                        # Silently discard dummy network pings and grab the next payload in queue
                        pass
                        
                if success:
                    break
                    
                logger.warning("Detected cache race. Instantly resetting page...")
                await browser.page.goto("about:blank")
                await asyncio.sleep(1)

            if not media or not album:
                raise TimeoutError(f"Failed to capture a parseable album payload for {url}")

            if not getattr(album, 'share_key', None) and url_share_key:
                album.share_key = url_share_key

            logger.info(f"Page 1: Scraped {len(media)} items using native '{valid_rpc_id}'.")

            current_cursor = media[-1].page_cursor if media else None
            page_count = 1

            while current_cursor:
                page_count += 1
                logger.info(f"Fetching Page {page_count} (Pagination)...")
                
                f_req = protocol.build_wQ6iqd_payload(album.id, current_cursor, album.share_key)
                
                try:
                    raw_response = await browser.fetch_batchexecute("wQ6iqd", f_req)
                    decoded = protocol.decode_wrbs(raw_response)
                    
                    new_media = []
                    for resp_rpc_id, resp_payload in decoded:
                        if resp_rpc_id in ("yQelMe", "wQ6iqd"):
                            new_media = parser.parse_album_listing(resp_rpc_id, resp_payload, album.id)
                            break
                    
                    if not new_media:
                        break 
                        
                    # GLOBAL DEDUPLICATION: Check incoming items against already scraped items
                    existing_ids = {m.media_id for m in media}
                    truly_new = [m for m in new_media if m.media_id not in existing_ids]
                    
                    media.extend(truly_new)
                    
                    overlap_count = len(new_media) - len(truly_new)
                    logger.info(f"Page {page_count}: Scraped {len(truly_new)} additional items (Ignored {overlap_count} overlapping items).")
                    
                    current_cursor = new_media[-1].page_cursor if new_media else None
                    
                except Exception as e:
                    logger.error(f"Failed to fetch page {page_count}: {e}")
                    break

            for m in media:
                m.album_name = album.title
                
                # Construct the permanent, publicly accessible web UI link
                if album.share_key:
                    m.public_url = f"https://photos.google.com/share/{album.id}/photo/{m.media_id}?key={album.share_key}"
                else:
                    m.public_url = f"https://photos.google.com/album/{album.id}/photo/{m.media_id}"

            self.db.save_album(album)
            self.db.save_many(media)

            logger.info(f"Fetching metadata for all {len(media)} items in batches concurrently...")
            media_ids = [m.media_id for m in media]
            chunk_size = 50
            
            sem = asyncio.Semaphore(3)
            
            async def process_batch(batch_num: int, chunk: list[str]) -> None:
                async with sem:
                    f_req = protocol.build_fDcn4b_batch(chunk, album.share_key or "")
                    
                    max_retries = 3
                    for attempt_b in range(max_retries):
                        try:
                            if attempt_b == 0:
                                await asyncio.sleep(batch_num * 0.2)
                                
                            raw_response = await browser.fetch_batchexecute("fDcn4b", f_req)
                            decoded = protocol.decode_wrbs(raw_response)
                            
                            batch_updates = []
                            for resp_rpc_id, resp_payload in decoded:
                                if resp_rpc_id == "fDcn4b":
                                    metadata = parser.parse_media_metadata(resp_payload)
                                    batch_updates.append(metadata)
                            
                            if not batch_updates:
                                raise Exception("Google returned 200 OK but stripped the data (Rate Limit).")

                            self.db.update_metadata_batch(batch_updates)
                            logger.info(f"Batch {batch_num}: Successfully parsed and updated {len(batch_updates)} items.")
                            break
                            
                        except Exception as e:
                            logger.warning(f"Batch {batch_num} failed (Attempt {attempt_b + 1}/{max_retries}): {e}")
                            if attempt_b == max_retries - 1:
                                logger.error(f"Max retries reached. Batch {batch_num} failed completely.")
                            
                            await asyncio.sleep(2 ** (attempt_b + 1))

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