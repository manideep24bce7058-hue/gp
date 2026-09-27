import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker

from models import Album, Media

# Attempt to load from config, fallback to environment variables/defaults
try:
    from config import LOCAL_DATABASE_URL, CLOUD_DATABASE_URL
except ImportError:
    LOCAL_DATABASE_URL = "sqlite:///google_photos.db"
    CLOUD_DATABASE_URL = os.environ.get("AIVEN_DB_URI", "sqlite:///google_photos_cloud.db")

Base = declarative_base()

class AlbumRecord(Base):
    __tablename__ = "albums"
    id = Column(String, primary_key=True)
    title = Column(String)
    share_key = Column(String)
    cover_url = Column(String)
    cover_width = Column(Integer)
    cover_height = Column(Integer)
    owner_id = Column(String)
    owner_name = Column(String)
    owner_avatar_url = Column(String)
    indexed_at = Column(DateTime, default=datetime.utcnow)

class MediaRecord(Base):
    __tablename__ = "media"
    media_id = Column(String, primary_key=True)
    album_id = Column(String)
    album_name = Column(String)
    filename = Column(String)
    preview_url = Column(String)
    stream_url = Column(String)
    download_url = Column(String)
    width = Column(Integer)
    height = Column(Integer)
    file_size_bytes = Column(BigInteger)
    capture_timestamp_ms = Column(BigInteger)
    added_timestamp_ms = Column(BigInteger)
    owner_id = Column(String)
    owner_name = Column(String)
    owner_avatar_url = Column(String)
    page_cursor = Column(String)
    indexed_at = Column(DateTime, default=datetime.utcnow)

class Database:
    def __init__(self) -> None:
        # Initialize Local Engine
        self.local_engine = create_engine(LOCAL_DATABASE_URL)
        self.LocalSession = sessionmaker(bind=self.local_engine)

        # Initialize Cloud Engine (Aiven)
        self.cloud_engine = create_engine(CLOUD_DATABASE_URL)
        self.CloudSession = sessionmaker(bind=self.cloud_engine)

    def create(self) -> None:
        Base.metadata.create_all(self.local_engine)
        Base.metadata.create_all(self.cloud_engine)
        
        self._create_views(self.local_engine)
        self._create_views(self.cloud_engine)

    def _create_views(self, engine) -> None:
        is_postgres = "postgres" in engine.dialect.name
        collation = "" if is_postgres else "COLLATE NOCASE"

        with engine.connect() as conn:
            conn.execute(text("DROP VIEW IF EXISTS vw_media_formatted;"))
            conn.execute(text("DROP VIEW IF EXISTS vw_album_storage;"))
            
            conn.execute(text(f"""
                CREATE VIEW vw_media_formatted AS
                SELECT 
                    COALESCE(a.title, 'Unallocated/No Album') AS "Album Title",
                    m.filename AS "Filename",
                    ROUND(m.file_size_bytes / 1073741824.0, 3) AS "Size (GB)",
                    CASE 
                        WHEN m.width IS NOT NULL AND m.height IS NOT NULL THEN m.width || 'x' || m.height
                        ELSE ''
                    END AS "Resolution",
                    m.media_id AS "Media ID",
                    'https://photos.google.com/share/' || m.album_id || '/photo/' || m.media_id || 
                    CASE WHEN a.share_key IS NOT NULL AND a.share_key != '' THEN '?key=' || a.share_key ELSE '' END AS "Share Link"
                FROM media m
                LEFT JOIN albums a ON m.album_id = a.id
                ORDER BY a.title {collation}, m.filename {collation};
            """))
            
            conn.execute(text("""
                CREATE VIEW vw_album_storage AS
                SELECT 
                    COALESCE(a.title, 'Unallocated/No Album') AS "Album Name",
                    COUNT(m.media_id) AS "Total Files",
                    ROUND(SUM(m.file_size_bytes) / 1048576.0, 2) AS "Size (MB)",
                    ROUND(SUM(m.file_size_bytes) / 1073741824.0, 2) AS "Size (GB)",
                    ROUND(SUM(m.file_size_bytes) / 1099511627776.0, 2) AS "Size (TB)"
                FROM media m
                LEFT JOIN albums a ON m.album_id = a.id
                GROUP BY m.album_id, a.title
                ORDER BY SUM(m.file_size_bytes) DESC;
            """))
            conn.commit()

    def _apply_album_fields(self, record: AlbumRecord, album: Album) -> None:
        record.title = album.title
        record.share_key = getattr(album, "share_key", None)
        record.cover_url = getattr(album, "cover_url", None)
        record.cover_width = getattr(album, "cover_width", None)
        record.cover_height = getattr(album, "cover_height", None)
        
        owner = getattr(album, "owner", None)
        if owner:
            record.owner_id = owner.id
            record.owner_name = owner.name
            record.owner_avatar_url = owner.avatar_url

    def save_album(self, album: Album) -> None:
        with self.LocalSession() as session:
            record = session.query(AlbumRecord).filter_by(id=album.id).first()
            if not record:
                record = AlbumRecord(id=album.id)
                session.add(record)
            self._apply_album_fields(record, album)
            session.commit()

        with self.CloudSession() as session:
            record = session.query(AlbumRecord).filter_by(id=album.id).first()
            if not record:
                record = AlbumRecord(id=album.id)
                session.add(record)
            self._apply_album_fields(record, album)
            session.commit()

    def _update_media_record(self, record: MediaRecord, media: Media) -> None:
        record.album_id = media.album_id
        record.album_name = getattr(media, "album_name", None)
        record.filename = media.filename
        record.preview_url = getattr(media, "preview_url", None)
        record.stream_url = getattr(media, "stream_url", None)
        record.download_url = getattr(media, "download_url", None)
        record.width = getattr(media, "width", None)
        record.height = getattr(media, "height", None)
        record.file_size_bytes = getattr(media, "file_size_bytes", None)
        record.capture_timestamp_ms = getattr(media, "capture_timestamp_ms", None)
        record.added_timestamp_ms = getattr(media, "added_timestamp_ms", None)
        record.page_cursor = getattr(media, "page_cursor", None)
        
        owner = getattr(media, "owner", None)
        if owner:
            record.owner_id = owner.id
            record.owner_name = owner.name
            record.owner_avatar_url = owner.avatar_url

    def save_many(self, media_list: list[Media]) -> None:
        with self.LocalSession() as session:
            for media in media_list:
                record = session.query(MediaRecord).filter_by(media_id=media.media_id).first()
                if not record:
                    record = MediaRecord(media_id=media.media_id)
                    session.add(record)
                self._update_media_record(record, media)
            session.commit()

        with self.CloudSession() as session:
            for media in media_list:
                record = session.query(MediaRecord).filter_by(media_id=media.media_id).first()
                if not record:
                    record = MediaRecord(media_id=media.media_id)
                    session.add(record)
                self._update_media_record(record, media)
            session.commit()

    def update_metadata_batch(self, media_list: list) -> None:
        with self.LocalSession() as session:
            self._apply_metadata_updates(session, media_list)
            session.commit()

        with self.CloudSession() as session:
            self._apply_metadata_updates(session, media_list)
            session.commit()

    def _apply_metadata_updates(self, session, media_list: list) -> None:
        for item in media_list:
            media_id = item.get("media_id") if isinstance(item, dict) else getattr(item, "media_id", None)
            if not media_id:
                continue

            record = session.query(MediaRecord).filter_by(media_id=media_id).first()
            if record:
                if isinstance(item, dict):
                    record.filename = item.get("filename") or record.filename
                    record.file_size_bytes = item.get("file_size_bytes") or record.file_size_bytes
                    record.width = item.get("width") or record.width
                    record.height = item.get("height") or record.height
                    record.stream_url = item.get("stream_url") or record.stream_url
                    record.download_url = item.get("download_url") or record.download_url
                else:
                    record.filename = getattr(item, "filename", None) or record.filename
                    record.file_size_bytes = getattr(item, "file_size_bytes", None) or record.file_size_bytes
                    record.width = getattr(item, "width", None) or record.width
                    record.height = getattr(item, "height", None) or record.height
                    record.stream_url = getattr(item, "stream_url", None) or record.stream_url
                    record.download_url = getattr(item, "download_url", None) or record.download_url