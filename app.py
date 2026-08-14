import asyncio
import logging

from indexer import GooglePhotosIndexer

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)

async def main():
    # Changed from /share/ to /album/ and removed the key parameter
    url = "https://photos.google.com/share/AF1QipPT0HmYT74nDyd-imxk07lN9biwEHJFmsMzka8x1nVosuFXO8LIRiXrydAWpzNA-w?key=ZFJnZU5Dck5hVEtZdEFQd3hoSlBmNk9fR0M2ZFJ3"
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