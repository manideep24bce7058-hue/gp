import sqlite3

def main():
    # Connect to your database (update the filename if necessary)
    conn = sqlite3.connect("google_photos.db")
    cursor = conn.cursor()

    # Execute the sum query
    cursor.execute("SELECT SUM(file_size_bytes) FROM media")
    total_bytes = cursor.fetchone()[0]

    if total_bytes is None:
        print("The database is empty or file sizes are missing.")
        return

    # Convert to human-readable formats
    total_gb = total_bytes / (1024 ** 3)
    total_tb = total_bytes / (1024 ** 4)

    print(f"Total Bytes: {total_bytes:,}")
    print(f"Total GB:    {total_gb:,.2f} GB")
    print(f"Total TB:    {total_tb:,.2f} TB")

    conn.close()

if __name__ == "__main__":
    main()