import asyncio
import logging
import sys
import json
import os
from datetime import datetime
from indexer import GooglePhotosIndexer
from database import Database, select, MediaRecord

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)

ALBUM_FILE = "album_links.txt"
SIZE_FILE = "size.json"

def load_all_albums(file_path: str) -> dict[str, str]:
    albums = {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if ":" in line:
                    name, url = line.split(":", 1)
                    albums[name.strip()] = url.strip().strip('"').strip("'")
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
    return albums

def format_size(bytes_size: int) -> str:
    if not bytes_size:
        return "0 MB"
    size = bytes_size / (1024 * 1024)
    if size < 1024:
        return f"{size:.2f} MB"
    elif size < 1024 * 1024:
        return f"{size / 1024:.2f} GB"
    else:
        return f"{size / (1024 * 1024):.2f} TB"

def update_size_file(album_name: str, total_bytes: int) -> None:
    data = {}
    if os.path.exists(SIZE_FILE):
        with open(SIZE_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                pass
                
    size_mb = total_bytes / (1024 ** 2)
    size_gb = total_bytes / (1024 ** 3)
    size_tb = total_bytes / (1024 ** 4)
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    data[album_name] = {
        "MB": round(size_mb, 2),
        "GB": round(size_gb, 2),
        "TB": round(size_tb, 2),
        "last_updated": current_time
    }
    
    with open(SIZE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
        
    print(f"Updated {SIZE_FILE}: {album_name} -> {data[album_name]['GB']} GB (Updated: {current_time})")
async def process_album(album_name: str, url: str, db: Database) -> None:
    print(f"\n--- Indexing Album: {album_name} ---")
    print(f"URL: {url}")
    
    indexer = GooglePhotosIndexer()
    try:
        result = await indexer.index(url)
        print("\nSuccess!")
        print(f"Album ID: {result.album.id}")
        print(f"Title:    {result.album.title}")
        print(f"Media:    {result.media_count} items stored")
        print(f"Time:     {result.elapsed_seconds:.2f}s")
        
        # Calculate total size from database records
        with db.LocalSession() as session:
            stmt = select(MediaRecord).where(MediaRecord.album_id == result.album.id)
            records = session.scalars(stmt).all()
            total_bytes = sum(r.file_size_bytes or 0 for r in records)
            
        update_size_file(album_name, total_bytes)
        
    except Exception as e:
        print(f"\nError processing {album_name}: {e}")

async def main() -> None:
    albums = load_all_albums(ALBUM_FILE)
    if not albums:
        return
        
    db = Database()
    targets = {}

    # Option C: Positional CLI Argument Parsing
    if len(sys.argv) > 1:
        target_name = sys.argv[1]
        if target_name in albums:
            targets[target_name] = albums[target_name]
        else:
            print(f"Error: Album '{target_name}' not found in {ALBUM_FILE}.")
            return
    else:
        targets = albums
        print(f"No specific album requested. Processing all {len(targets)} albums...")

    for name, url in targets.items():
        await process_album(name, url, db)

if __name__ == "__main__":
    asyncio.run(main())