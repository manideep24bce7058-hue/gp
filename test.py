from database import Database

def main():
    db = Database()
    media_items = db.all()
    
    if not media_items:
        print("No media found in the database.")
        return

    print(f"Found {len(media_items)} items in the database. Generating test links...")
    
    with open("test.txt", "w", encoding="utf-8") as f:
        for item in media_items:
            if item.preview_url:
                # Append =dv for the video stream
                stream_link = f"{item.preview_url}=dv"
                
                # Append =d for the direct download
                download_link = f"{item.preview_url}=d"
                
                f.write(f"ID: {item.media_id}\n")
                if item.filename:
                    f.write(f"Filename: {item.filename}\n")
                f.write(f"Stream:   {stream_link}\n")
                f.write(f"Download: {download_link}\n")
                f.write("-" * 60 + "\n")
    
    print("Successfully saved links to 'test_links.txt'.")
    print("Open the file and test the massive URLs in your custom player!")

if __name__ == "__main__":
    main()