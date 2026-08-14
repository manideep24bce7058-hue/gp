from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from sqlalchemy import BigInteger, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import SQLALCHEMY_DATABASE_URL
from models import Album, Media, Owner


class Base(DeclarativeBase):
    pass


class AlbumRecord(Base):
    __tablename__ = "albums"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    share_key: Mapped[Optional[str]] = mapped_column(String)
    cover_url: Mapped[Optional[str]] = mapped_column(String)
    cover_width: Mapped[Optional[int]] = mapped_column(Integer)
    cover_height: Mapped[Optional[int]] = mapped_column(Integer)
    owner_id: Mapped[Optional[str]] = mapped_column(String)
    owner_name: Mapped[Optional[str]] = mapped_column(String)
    owner_avatar_url: Mapped[Optional[str]] = mapped_column(String)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MediaRecord(Base):
    __tablename__ = "media"

    media_id: Mapped[str] = mapped_column(String, primary_key=True)
    preview_url: Mapped[Optional[str]] = mapped_column(String)
    stream_url: Mapped[Optional[str]] = mapped_column(String)
    download_url: Mapped[Optional[str]] = mapped_column(String)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    capture_timestamp_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    added_timestamp_ms: Mapped[Optional[int]] = mapped_column(BigInteger)
    album_id: Mapped[Optional[str]] = mapped_column(String)
    owner_id: Mapped[Optional[str]] = mapped_column(String)
    owner_name: Mapped[Optional[str]] = mapped_column(String)
    owner_avatar_url: Mapped[Optional[str]] = mapped_column(String)
    page_cursor: Mapped[Optional[str]] = mapped_column(String)
    filename: Mapped[Optional[str]] = mapped_column(String)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    indexed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Database:
    def __init__(self) -> None:
        self.engine = create_engine(SQLALCHEMY_DATABASE_URL)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def create(self) -> None:
        Base.metadata.create_all(self.engine)

    @staticmethod
    def _extract_owner(record: AlbumRecord | MediaRecord) -> Optional[Owner]:
        if not record.owner_id:
            return None
        return Owner(
            id=record.owner_id,
            name=record.owner_name or "",
            avatar_url=record.owner_avatar_url,
        )

    @staticmethod
    def _apply_owner(record: AlbumRecord | MediaRecord, owner: Optional[Owner]) -> None:
        if owner:
            record.owner_id = owner.id
            record.owner_name = owner.name
            record.owner_avatar_url = owner.avatar_url
        else:
            record.owner_id = None
            record.owner_name = None
            record.owner_avatar_url = None

    @classmethod
    def _to_album_model(cls, record: AlbumRecord) -> Album:
        return Album(
            id=record.id,
            title=record.title,
            share_key=record.share_key,
            cover_url=record.cover_url,
            cover_width=record.cover_width,
            cover_height=record.cover_height,
            owner=cls._extract_owner(record),
        )

    @classmethod
    def _update_album_record(cls, record: AlbumRecord, album: Album) -> None:
        record.title = album.title
        record.share_key = album.share_key
        record.cover_url = album.cover_url
        record.cover_width = album.cover_width
        record.cover_height = album.cover_height
        cls._apply_owner(record, album.owner)

    @classmethod
    def _to_media_model(cls, record: MediaRecord) -> Media:
        return Media(
            media_id=record.media_id,
            preview_url=record.preview_url,
            stream_url=record.stream_url,
            download_url=record.download_url,
            width=record.width,
            height=record.height,
            capture_timestamp_ms=record.capture_timestamp_ms,
            added_timestamp_ms=record.added_timestamp_ms,
            album_id=record.album_id,
            owner=cls._extract_owner(record),
            page_cursor=record.page_cursor,
            filename=record.filename,
            file_size_bytes=record.file_size_bytes,
            indexed_at=record.indexed_at,
        )

    @classmethod
    def _update_media_record(cls, record: MediaRecord, media: Media) -> None:
        record.preview_url = media.preview_url
        record.stream_url = media.stream_url
        record.download_url = media.download_url
        record.width = media.width
        record.height = media.height
        record.capture_timestamp_ms = media.capture_timestamp_ms
        record.added_timestamp_ms = media.added_timestamp_ms
        record.album_id = media.album_id
        record.page_cursor = media.page_cursor
        record.filename = media.filename
        record.file_size_bytes = media.file_size_bytes
        cls._apply_owner(record, media.owner)

    def save_album(self, album: Album) -> None:
        with self.Session() as db:
            record = db.get(AlbumRecord, album.id)
            if record is None:
                record = AlbumRecord(id=album.id)
                db.add(record)
            self._update_album_record(record, album)
            db.commit()

    def get_album(self, album_id: str) -> Optional[Album]:
        with self.Session() as db:
            record = db.get(AlbumRecord, album_id)
            if record is None:
                return None
            return self._to_album_model(record)

    def all_albums(self) -> list[Album]:
        with self.Session() as db:
            records = db.scalars(select(AlbumRecord)).all()
            return [self._to_album_model(r) for r in records]

    def save(self, media: Media) -> None:
        with self.Session() as db:
            record = db.get(MediaRecord, media.media_id)
            if record is None:
                record = MediaRecord(media_id=media.media_id)
                db.add(record)
            self._update_media_record(record, media)
            db.commit()

    def save_many(self, media_list: list[Media]) -> None:
        if not media_list:
            return

        media_ids = [m.media_id for m in media_list]

        with self.Session() as db:
            stmt = select(MediaRecord).where(MediaRecord.media_id.in_(media_ids))
            existing_records = {r.media_id: r for r in db.scalars(stmt).all()}

            for media in media_list:
                record = existing_records.get(media.media_id)
                if record is None:
                    record = MediaRecord(media_id=media.media_id)
                    db.add(record)
                self._update_media_record(record, media)

            db.commit()
            
    def update_metadata(self, media_id: str, metadata: dict[str, Any]) -> None:
        with self.Session() as db:
            record = db.get(MediaRecord, media_id)
            if record:
                if "filename" in metadata:
                    record.filename = metadata["filename"]
                if "file_size_bytes" in metadata:
                    record.file_size_bytes = metadata["file_size_bytes"]
                db.commit()

    def get(self, media_id: str) -> Optional[Media]:
        with self.Session() as db:
            record = db.get(MediaRecord, media_id)
            if record is None:
                return None
            return self._to_media_model(record)

    def all(self) -> list[Media]:
        with self.Session() as db:
            records = db.scalars(select(MediaRecord)).all()
            return [self._to_media_model(r) for r in records]