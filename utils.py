from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse


def parse_shared_album_url(url: str) -> tuple[str, str]:
    """
    Parse a Google Photos shared album URL.

    Returns
    -------
    (album_id, share_key)

    Raises
    ------
    ValueError
        If the URL is invalid.
    """

    parsed = urlparse(url)

    parts = [part for part in parsed.path.split("/") if part]

    if len(parts) < 2 or parts[0] != "share":
        raise ValueError("Invalid Google Photos shared album URL.")

    album_id = parts[1]

    share_key = parse_qs(parsed.query).get("key", [""])[0]

    if not share_key:
        raise ValueError("Missing album share key.")

    return album_id, share_key


def timestamp_to_datetime(timestamp_ms: int | None) -> datetime | None:
    """
    Convert a Unix timestamp in milliseconds to UTC datetime.
    """

    if timestamp_ms is None:
        return None

    return datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    )


def datetime_to_timestamp(dt: datetime | None) -> int | None:
    """
    Convert a datetime to Unix milliseconds.
    """

    if dt is None:
        return None

    return int(dt.timestamp() * 1000)


def format_resolution(width: int | None, height: int | None) -> str | None:
    """
    Format width × height.
    """

    if width is None or height is None:
        return None

    return f"{width}×{height}"


def chunks(sequence: list, size: int):
    """
    Yield successive chunks from a list.
    """

    if size <= 0:
        raise ValueError("size must be > 0")

    for i in range(0, len(sequence), size):
        yield sequence[i:i + size]