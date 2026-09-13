import os
import sqlite3

def calculate_album_sizes(db_path):
    if not os.path.exists(db_path):
        print(f"Error: Database file '{db_path}' not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query to join media and albums table, and sum the file sizes grouped by album id
        query = """
            SELECT 
                COALESCE(a.title, 'Unallocated/No Album') AS album_name,
                SUM(m.file_size_bytes) AS total_bytes,
                COUNT(m.media_id) AS total_files
            FROM media m
            LEFT JOIN albums a ON m.album_id = a.id
            GROUP BY m.album_id;
        """

        cursor.execute(query)
        results = cursor.fetchall()

        # Added Size (TB) column to the header template
        print(f"{'Album Name':<30} | {'Files':<6} | {'Size (MB)':<12} | {'Size (GB)':<12} | {'Size (TB)':<10}")
        print("-" * 80)

        for row in results:
            album_name, total_bytes, total_files = row
            
            if total_bytes is None:
                total_bytes = 0

            # Conversion math based on standard 1024 scale
            size_mb = total_bytes / (1024 ** 2)
            size_gb = total_bytes / (1024 ** 3)
            size_tb = total_bytes / (1024 ** 4)  # 1 TB = 1024 GB

            print(f"{album_name:<30} | {total_files:<6} | {size_mb:<12.2f} | {size_gb:<12.2f} | {size_tb:<10.2f} TB")

    except sqlite3.Error as e:
        print(f"An error occurred while querying the database: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Ensure this matches the exact name of your sqlite database file in the directory
    database_file = "google_photos.db" 
    calculate_album_sizes(database_file)
'''
last calculated on: 2026-09-13
Album Name                     | Files  | Size (MB)    | Size (GB)    | Size (TB) 
--------------------------------------------------------------------------------
Movies                         | 295    | 6173759.65   | 6029.06      | 5.89       TB
MCU                            | 48     | 2324473.51   | 2269.99      | 2.22       TB

'''