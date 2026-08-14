from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Owner:
    id: str
    name: str
    avatar_url: Optional[str] = None


@dataclass(slots=True)
class Album:
    id: str
    title: str
    share_key: Optional[str] = None
    cover_url: Optional[str] = None
    cover_width: Optional[int] = None
    cover_height: Optional[int] = None
    owner: Optional[Owner] = None


@dataclass(slots=True)
class Media:
    media_id: str
    preview_url: Optional[str] = None
    stream_url: Optional[str] = None
    download_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    capture_timestamp_ms: Optional[int] = None
    added_timestamp_ms: Optional[int] = None
    album_id: Optional[str] = None
    owner: Optional[Owner] = None
    page_cursor: Optional[str] = None
    filename: Optional[str] = None
    file_size_bytes: Optional[int] = None
    indexed_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def resolution(self) -> Optional[str]:
        if self.width is None or self.height is None:
            return None
        return f"{self.width}×{self.height}"