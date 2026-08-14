import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load the Aiven URI from your .env file
load_dotenv()
cloud_url = os.getenv("CLOUD_DATABASE_URL")

def verify_cloud_data():
    if not cloud_url:
        print("Error: CLOUD_DATABASE_URL not found in .env")
        return

    print("Connecting to Aiven Cloud Database...")
    engine = create_engine(cloud_url)
    
    try:
        with engine.connect() as conn:
            # Query the row counts directly using raw SQL
            album_count = conn.scalar(text("SELECT COUNT(*) FROM albums"))
            media_count = conn.scalar(text("SELECT COUNT(*) FROM media"))
            
            print("\n--- Cloud Database Status ---")
            print(f"Albums synced: {album_count}")
            print(f"Media items synced: {media_count}")
            print("-----------------------------\n")
            print("Verification successful. Data is live.")
            
    except Exception as e:
        print(f"Connection or execution failed: {e}")

if __name__ == "__main__":
    verify_cloud_data()