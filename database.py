import sqlite3
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, text
from sqlalchemy.orm import declarative_base, sessionmaker

from models import Album, Media

Base = declarative_base()

class AlbumRecord(Base):
    __tablename__ = "albums"
    id = Column(String, primary_key=True)
    title = Column(String)
    share_key = Column(String)

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

class Database:
    def __init__(self, local_path: str = "sqlite:///google_photos.db"):
        self.local_engine = create_engine(local_path)
        self.LocalSession = sessionmaker(bind=self.local_engine)

    def create(self) -> None:
        Base.metadata.create_all(self.local_engine)
        self._create_views()

    def _create_views(self) -> None:
        with self.local_engine.connect() as conn:
            conn.execute(text("DROP VIEW IF EXISTS vw_media_formatted;"))
            conn.execute(text("DROP VIEW IF EXISTS vw_album_storage;"))
            
            # View 1: Formatted Media (Permanent Links only, safe resolution parsing)
            conn.execute(text("""
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
                ORDER BY a.title COLLATE NOCASE, m.filename COLLATE NOCASE;
            """))
            
            # View 2: Storage Summary
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
                GROUP BY m.album_id
                ORDER BY SUM(m.file_size_bytes) DESC;
            """))
            conn.commit()

    def save_album(self, album: Album) -> None:
        with self.LocalSession() as session:
            record = session.query(AlbumRecord).filter_by(id=album.id).first()
            if not record:
                record = AlbumRecord(id=album.id)
                session.add(record)
            record.title = album.title
            record.share_key = getattr(album, "share_key", None)
            session.commit()

    def save_many(self, media_list: list[Media]) -> None:
        with self.LocalSession() as session:
            for media in media_list:
                record = session.query(MediaRecord).filter_by(media_id=media.media_id).first()
                if not record:
                    record = MediaRecord(media_id=media.media_id)
                    session.add(record)
                
                record.album_id = media.album_id
                record.album_name = getattr(media, "album_name", None)
                record.filename = media.filename
                record.preview_url = getattr(media, "preview_url", None)
                record.stream_url = getattr(media, "stream_url", None)
                record.download_url = getattr(media, "download_url", None)
                record.width = getattr(media, "width", None)
                record.height = getattr(media, "height", None)
                record.file_size_bytes = getattr(media, "file_size_bytes", None)
            
            session.commit()

    def update_metadata_batch(self, media_list: list) -> None:
        with self.LocalSession() as session:
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
            session.commit()