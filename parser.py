from __future__ import annotations

import logging
from typing import Any

import protocol
from models import Album, Media, Owner

logger = logging.getLogger(__name__)

Payload = list[Any]

META_ID = 0
META_FILENAME = 2
META_SIZE = 5

class GooglePhotosParser:
    @staticmethod
    def _parse_preview(data: list[Any] | None) -> tuple[str | None, int | None, int | None]:
        if not data or not isinstance(data, list) or len(data) < 3:
            return None, None, None
        return data[0], data[1], data[2]

    def parse_album_metadata(self, rpc_id: str, payload: Payload) -> Album:
        try:
            if rpc_id == "frGlJf":
                album_data = payload[0][5][0]
                cover_url, cover_width, cover_height = self._parse_preview(album_data[2])
                
                owner = None
                if len(album_data) > 12 and album_data[12] and len(album_data[12]) > 0:
                    owner_info = album_data[12][0][0]
                    owner = Owner(
                        id=owner_info[1],
                        name=album_data[12][0][3][0],
                        avatar_url=album_data[12][0][11][0],
                    )

                return Album(
                    id=album_data[6],
                    title=album_data[1],
                    share_key=album_data[7] if len(album_data) > 7 else None,
                    cover_url=cover_url,
                    cover_width=cover_width,
                    cover_height=cover_height,
                    owner=owner,
                )

            elif rpc_id == "snAcKc":
                album_data = payload[3]
                cover_url, cover_width, cover_height = self._parse_preview(album_data[4])
                
                owner = None
                owner_list = album_data[5]
                if isinstance(owner_list, list) and len(owner_list) >= 3:
                    avatar = owner_list[12][0] if len(owner_list) > 12 and isinstance(owner_list[12], list) else None
                    owner = Owner(
                        id=owner_list[1],
                        name=owner_list[2],
                        avatar_url=avatar
                    )

                share_key = album_data[12] if len(album_data) > 12 and isinstance(album_data[12], str) else None

                return Album(
                    id=album_data[0],
                    title=album_data[1],
                    share_key=share_key,
                    cover_url=cover_url,
                    cover_width=cover_width,
                    cover_height=cover_height,
                    owner=owner,
                )

            else:
                raise protocol.ProtocolError(f"Unsupported RPC ID for album metadata: {rpc_id}")

        except (IndexError, TypeError) as e:
            raise protocol.ProtocolError(f"Unexpected {rpc_id} album structure: {e}") from e

    def parse_album_listing(self, rpc_id: str, payload: Payload, album_id: str | None = None) -> list[Media]:
        media_items: list[Media] = []

        try:
            # 1. EXTRACT PAGINATION CURSOR
            cursor = None
            if rpc_id in ("yQelMe", "wQ6iqd"):
                for param in payload[2:]:
                    if isinstance(param, str) and param != album_id and len(param) > 30 and not param.startswith("http"):
                        cursor = param
                        break
            elif rpc_id == "frGlJf":
                for page in payload:
                    if isinstance(page, list) and len(page) > 0 and isinstance(page[0], str) and len(page[0]) > 30:
                        cursor = page[0]
                        break
            elif rpc_id == "snAcKc":
                cursor = payload[2] if len(payload) > 2 and isinstance(payload[2], str) else None

            # 2. RECURSIVE MEDIA SCANNER: Dynamically hunt for items matching the signature
            raw_items = []
            def _extract(data: Any) -> None:
                if not isinstance(data, list): return
                
                # Signature Check: Does this block look like a media item?
                if len(data) >= 2:
                    id_p = data[0]
                    m_id = id_p if isinstance(id_p, str) and id_p.startswith("AF1Q") else (id_p[0] if isinstance(id_p, list) and len(id_p) > 0 and isinstance(id_p[0], str) and id_p[0].startswith("AF1Q") else None)
                    
                    if m_id:
                        u_p = data[1]
                        u = u_p if isinstance(u_p, str) and u_p.startswith("http") else (u_p[0] if isinstance(u_p, list) and len(u_p) > 0 and isinstance(u_p[0], str) and u_p[0].startswith("http") else None)
                        
                        if u:
                            raw_items.append(data)
                            return # Block matched. Stop recursing deeper.

                # If no match, keep digging
                for elem in data:
                    if isinstance(elem, list):
                        _extract(elem)

            _extract(payload)

            # 3. PARSE THE IDENTIFIED ITEMS
            for item in raw_items:
                media_id = item[0][0] if isinstance(item[0], list) else item[0]

                base_url = None
                if isinstance(item[1], list) and len(item[1]) > 0:
                    base_url = item[1][0]
                elif isinstance(item[1], str):
                    base_url = item[1]

                width, height = None, None
                if isinstance(item[1], list) and len(item[1]) >= 3:
                    if isinstance(item[1][1], int) and isinstance(item[1][2], int):
                        width, height = item[1][1], item[1][2]

                # Recursive Video URL hunt
                def _search_vid(d: Any) -> str | None:
                    if isinstance(d, dict) and "76647426" in d:
                        v_meta = d["76647426"]
                        if isinstance(v_meta, list) and len(v_meta) > 13 and isinstance(v_meta[13], list) and len(v_meta[13]) > 0:
                            return v_meta[13][0]
                    elif isinstance(d, list):
                        for e in d:
                            res = _search_vid(e)
                            if res: return res
                    return None

                video_url = _search_vid(item)
                final_url = video_url or base_url

                # Unified Timestamp hunt (13-digit Unix MS)
                ts_set = set()
                def _get_ts(d: Any) -> None:
                    if isinstance(d, int) and d > 1000000000000:
                        ts_set.add(d)
                    elif isinstance(d, list):
                        for e in d: _get_ts(e)
                _get_ts(item)

                ts_list = sorted(list(ts_set))
                capture_ts = ts_list[0] if len(ts_list) > 0 else None
                added_ts = ts_list[1] if len(ts_list) > 1 else capture_ts

                media_items.append(Media(
                    media_id=media_id,
                    preview_url=final_url,
                    stream_url=f"{final_url}=dv" if final_url else None,
                    download_url=f"{final_url}=d" if final_url else None,
                    width=width,
                    height=height,
                    capture_timestamp_ms=capture_ts,
                    added_timestamp_ms=added_ts,
                    album_id=album_id,
                    page_cursor=cursor,
                ))

            # Deduplicate by media_id to filter out Google's redundant UI blocks
            unique_media = {m.media_id: m for m in media_items}
            return list(unique_media.values())

        except Exception as e:
            logger.exception(f"Error parsing media list for {rpc_id}: {e}")
            raise protocol.ProtocolError(f"Unexpected {rpc_id} media list structure: {e}") from e

    def parse_media_metadata(self, payload: Payload) -> dict[str, Any]:
        try:
            data = payload[0]
            return {
                "media_id": data[META_ID],
                "filename": data[META_FILENAME],
                "file_size_bytes": data[META_SIZE],
            }
        except (IndexError, TypeError) as e:
            raise protocol.ProtocolError(f"Unexpected fDcn4b metadata structure: {e}") from e