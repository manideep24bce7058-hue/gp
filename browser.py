from __future__ import annotations

import asyncio
import copy
import hashlib
import logging
from collections import deque
from typing import Any

from playwright.async_api import (
    BrowserContext,
    ConsoleMessage,
    Error,
    Page,
    Response,
    async_playwright,
)

import protocol

logger = logging.getLogger(__name__)


class GooglePhotosBrowser:
    def __init__(self, headless: bool = True, user_data_dir: str = "./chrome_data") -> None:
        self.headless = headless
        self.user_data_dir = user_data_dir
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        self._all_rpcs_queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._latest_payloads: dict[str, deque[Any]] = {}
        self._condition = asyncio.Condition()
        self._seen_hashes: set[tuple[str, bytes]] = set()
        self._seen_history: deque[tuple[str, bytes]] = deque(maxlen=200)
        self._ssr_task: asyncio.Task | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not initialized.")
        return self._page

    async def __aenter__(self) -> "GooglePhotosBrowser":
        logger.info("Launching Playwright Chromium (Persistent Context)...")
        self._playwright = await async_playwright().start()
        
        # Use a persistent context to save login cookies and session data
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            viewport={"width": 1600, "height": 1200},
            locale="en-US",
        )
        
        # Persistent contexts automatically come with one page
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        logger.info("[JS BRIDGE] Injecting AF_initDataCallback interceptor...")
        await self._page.add_init_script("""
            window._capturedInitData = {};
            let _af = undefined;
            Object.defineProperty(window, 'AF_initDataCallback', {
                get: function() {
                    return function(obj) {
                        try {
                            if (obj && obj.key) {
                                let d = obj.data;
                                if (typeof d === 'function') d = d();
                                window._capturedInitData[obj.key] = d;
                            }
                        } catch (e) {
                            console.error("Intercept error", e);
                        }
                        if (_af) return _af.apply(this, arguments);
                    };
                },
                set: function(val) { _af = val; },
                configurable: true
            });
        """)

        self._attach_events(self._page)
        self._ssr_task = asyncio.create_task(self._poll_ssr_payloads())
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        logger.info("Closing Playwright browser...")
        if self._ssr_task:
            self._ssr_task.cancel()
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    def _attach_events(self, page: Page) -> None:
        page.on("pageerror", self._on_page_error)
        page.on("console", self._on_console_message)
        page.on("response", self._on_response)

    def _on_page_error(self, error: Error) -> None:
        logger.error(f"Page error: {error}")

    def _on_console_message(self, msg: ConsoleMessage) -> None:
        if msg.type in ("error", "warning"):
            logger.debug(f"Console [{msg.type}]: {msg.text}")

    async def _on_response(self, response: Response) -> None:
        if "batchexecute" not in response.url and "/$rpc/" not in response.url:
            return
        if not response.ok:
            return

        try:
            text = await response.text()
            decoded_rpcs = protocol.decode_wrbs(text)
            if not decoded_rpcs:
                return

            # Explicitly allow only the required RPC IDs
            allowed_rpcs = {"snAcKc", "frGlJf", "fDcn4b"}

            for rpc_id, payload in decoded_rpcs:
                if rpc_id in allowed_rpcs:
                    await self._store_payload(rpc_id, payload, text, source="NETWORK")

        except protocol.ProtocolError as e:
            logger.debug("Failed to decode batchexecute: %s", e)
        except Exception as e:
            # Catch the Playwright TargetClosedError when browser shuts down
            if "TargetClosedError" in str(type(e)) or "Target page, context or browser has been closed" in str(e):
                pass
            else:
                logger.exception("Unexpected error extracting RPCs")        
    async def _poll_ssr_payloads(self) -> None:
        while True:
            try:
                if not self._page or self._page.is_closed():
                    break
                await self._extract_ssr_payloads()
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[SSR] Polling error: {e}")
                await asyncio.sleep(0.5)

    async def _extract_ssr_payloads(self) -> None:
        try:
            captured_data = await self.page.evaluate("window._capturedInitData")
        except Exception:
            return

        if not captured_data:
            return

        for key, data in captured_data.items():
            if not isinstance(data, list):
                continue

            if len(data) >= 4 and isinstance(data[1], list) and isinstance(data[3], list):
                if len(data[3]) > 6 and isinstance(data[3][0], str) and data[3][0].startswith("AF1Q"):
                    await self._store_payload("snAcKc", data, f"ssr_{key}", source="JS-BRIDGE")
                    continue

            if len(data) > 0 and isinstance(data[0], list) and len(data[0]) > 6:
                if isinstance(data[0][5], list) and isinstance(data[0][6], list):
                    album_meta = data[0][5]
                    if len(album_meta) > 0 and isinstance(album_meta[0], list) and len(album_meta[0]) > 6:
                        if isinstance(album_meta[0][6], str) and album_meta[0][6].startswith("AF1Q"):
                            await self._store_payload("frGlJf", data, f"ssr_{key}", source="JS-BRIDGE")
                            continue

    async def _store_payload(self, rpc_id: str, payload: Any, raw_text: str, source: str) -> None:
        text_hash = hashlib.blake2b(raw_text.encode(), digest_size=16).digest()
        dedupe_key = (rpc_id, text_hash)

        async with self._condition:
            if dedupe_key in self._seen_hashes:
                return

            if len(self._seen_history) == self._seen_history.maxlen:
                oldest = self._seen_history.popleft()
                self._seen_hashes.remove(oldest)

            self._seen_history.append(dedupe_key)
            self._seen_hashes.add(dedupe_key)

            if rpc_id not in self._latest_payloads:
                self._latest_payloads[rpc_id] = deque(maxlen=10)
            self._latest_payloads[rpc_id].append(payload)

            await self._all_rpcs_queue.put((rpc_id, payload))
            logger.info(f"[{source}] Intercepted target payload: {rpc_id}!")
            self._condition.notify_all()

    async def fetch_batchexecute(self, rpc_id: str, f_req: str) -> str:
        logger.info(f"Sending active request for RPC: {rpc_id}...")
        
        at_token = await self.page.evaluate('window.WIZ_global_data ? window.WIZ_global_data.SNlM0e : ""')
        
        data = {"f.req": f_req}
        if at_token:
            data["at"] = at_token
            
        url = f"https://photos.google.com/_/PhotosUi/data/batchexecute?rpcids={rpc_id}&soc-app=165&soc-platform=1&soc-device=1&rt=c"
        
        if self._context is None:
            raise RuntimeError("Browser context is missing.")
            
        response = await self._context.request.post(
            url,
            form=data,
            headers={
                "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
            }
        )
        
        if not response.ok:
            raise Exception(f"Active batchexecute request failed with status: {response.status}")
            
        return await response.text()

    async def navigate(self, url: str, timeout: float = 30000.0) -> None:
        logger.info(f"Navigating to {url} ...")
        await self.page.goto(url, wait_until="domcontentloaded", timeout=timeout)

    async def wait_for_rpc(self, rpc_ids: str | list[str], timeout: float = 30.0) -> tuple[str, Any]:
        if isinstance(rpc_ids, str):
            rpc_ids = [rpc_ids]

        logger.info(f"Waiting for any of {rpc_ids} (timeout={timeout}s)...")

        def _predicate() -> str | None:
            for rpc_id in rpc_ids:
                if rpc_id in self._latest_payloads and len(self._latest_payloads[rpc_id]) > 0:
                    return rpc_id
            return None

        async with self._condition:
            found_id = _predicate()
            if not found_id:
                try:
                    await asyncio.wait_for(self._condition.wait_for(_predicate), timeout=timeout)
                    found_id = _predicate()
                except asyncio.TimeoutError as e:
                    raise TimeoutError(f"Timed out waiting for {rpc_ids} after {timeout} seconds.") from e
                    
            logger.info(f"Successfully delivered '{found_id}' to indexer.")
            return found_id, copy.deepcopy(self._latest_payloads[found_id][-1])