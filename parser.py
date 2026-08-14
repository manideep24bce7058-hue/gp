from __future__ import annotations

import logging
from typing import Any

import protocol
from models import Album, Media, Owner

logger = logging.getLogger(__name__)

Payload = list[Any]
PreviewData = list[Any]

# --- fDcn4b Indices ---
META_ID = 0
META_FILENAME = 2
META_SIZE = 5

class GooglePhotosParser:
    @staticmethod
    def _parse_preview(data: PreviewData | None) -> tuple[str | None, int | None, int | None]:
        if not data or not isinstance(data, list) or len(data) < 3:
            return None, None, None
        return data[0], data[1], data[2]

    @staticmethod
    def _extract_video_url(item: list[Any]) -> str | None:
        for element in item:
            if isinstance(element, dict) and "76647426" in element:
                video_meta = element["76647426"]
                if isinstance(video_meta, list) and len(video_meta) > 13:
                    url_list = video_meta[13]
                    if isinstance(url_list, list) and len(url_list) > 0:
                        return url_list[0]
        return None

    def parse_album_metadata(self, rpc_id: str, payload: Payload) -> Album:
        try:
            if rpc_id == "frGlJf":
                album_data = payload[0][5][0]
                cover_url, cover_width, cover_height = self._parse_preview(album_data[2])
                
                owner = None
                if album_data[12] and len(album_data[12]) > 0:
                    owner_info = album_data[12][0][0]
                    owner = Owner(
                        id=owner_info[1],
                        name=album_data[12][0][3][0],
                        avatar_url=album_data[12][0][11][0],
                    )

                return Album(
                    id=album_data[6],
                    title=album_data[1],
                    share_key=album_data[7],
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
            if rpc_id == "frGlJf":
                for page in payload:
                    cursor = page[0]
                    current_album_id = album_id or page[5][0][6]
                    
                    items = page[6]
                    if not items:
                        continue

                    for item in items:
                        preview_url, width, height = self._parse_preview(item[1])
                        video_url = self._extract_video_url(item)
                        base_url = video_url or preview_url
                        
                        media_items.append(Media(
                            media_id=item[0],
                            preview_url=base_url,
                            stream_url=f"{base_url}=dv" if base_url else None,
                            download_url=f"{base_url}=d" if base_url else None,
                            width=width,
                            height=height,
                            capture_timestamp_ms=item[2],
                            added_timestamp_ms=item[5],
                            album_id=current_album_id,
                            page_cursor=cursor,
                        ))

            elif rpc_id == "snAcKc":
                items = payload[1]
                if not items:
                    return []

                for item in items:
                    preview_url, width, height = self._parse_preview(item[1])
                    video_url = self._extract_video_url(item)
                    base_url = video_url or preview_url
                    
                    media_items.append(Media(
                        media_id=item[0],
                        preview_url=base_url,
                        stream_url=f"{base_url}=dv" if base_url else None,
                        download_url=f"{base_url}=d" if base_url else None,
                        width=width,
                        height=height,
                        capture_timestamp_ms=item[2],
                        added_timestamp_ms=item[5],
                        album_id=album_id,
                        page_cursor=None, 
                    ))

            return media_items

        except (IndexError, TypeError) as e:
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