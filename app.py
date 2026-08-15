import asyncio
import logging

from indexer import GooglePhotosIndexer

# Change this name to select which album to scrape from album_links.txt
TARGET_ALBUM_NAME = "Movies"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)

def get_url_from_file(file_path: str, target_name: str) -> str | None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(f"{target_name}:"):
                    # Split at the first colon and clean whitespace/quotes
                    url_part = line.split(":", 1)[1].strip()
                    return url_part.strip('"')
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
    return None

async def main():
    url = get_url_from_file("album_links.txt", TARGET_ALBUM_NAME)
    
    if not url:
        print(f"Error: Could not find a valid URL for '{TARGET_ALBUM_NAME}' in album_links.txt")
        return

    print(f"\nIndexing Album: {url}")
    
    indexer = GooglePhotosIndexer()
    try:
        result = await indexer.index(url)
        print("\nSuccess!")
        print(f"Album ID: {result.album.id}")
        print(f"Title:    {result.album.title}")
        print(f"Media:    {result.media_count} items stored")
        print(f"Time:     {result.elapsed_seconds:.2f}s")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    asyncio.run(main())