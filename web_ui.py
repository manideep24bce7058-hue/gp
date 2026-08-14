from flask import Flask, render_template_string, request
from sqlalchemy import select
from database import Database, MediaRecord

app = Flask(__name__)
db = Database()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Google Photos - Local Media Search</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; color: #333; margin: 0; padding: 20px; }
        .container { max-width: 900px; margin: 0 auto; }
        h1 { color: #1a73e8; }
        .search-box { display: flex; gap: 10px; margin-bottom: 30px; }
        input[type="text"] { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; }
        input[type="submit"] { padding: 12px 24px; border: none; background-color: #1a73e8; color: white; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold;}
        input[type="submit"]:hover { background-color: #1557b0; }
        .card { background: white; padding: 20px; margin-bottom: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .card h3 { margin-top: 0; word-break: break-all; font-size: 18px;}
        .meta { color: #666; font-size: 14px; margin-bottom: 15px; }
        video { width: 100%; border-radius: 8px; background: #000; outline: none; margin-bottom: 15px; }
        .actions a { display: inline-block; margin-right: 15px; text-decoration: none; font-size: 14px; font-weight: bold; color: #1a73e8; padding: 8px 12px; border: 1px solid #1a73e8; border-radius: 5px; transition: all 0.2s;}
        .actions a:hover { background-color: #1a73e8; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Local Media Search</h1>
        <form class="search-box" method="GET" action="/">
            <input type="text" name="q" placeholder="Search for a movie or filename..." value="{{ query }}">
            <input type="submit" value="Search">
        </form>

        {% if query and not results %}
            <p>No results found for "<strong>{{ query }}</strong>".</p>
        {% endif %}

        {% for item in results %}
            <div class="card">
                <h3>{{ item.filename or 'Unknown Filename' }}</h3>
                <div class="meta">
                    <strong>Resolution:</strong> {{ item.resolution or 'Unknown' }} &nbsp;|&nbsp; 
                    <strong>Size:</strong> {{ (item.file_size_bytes / 1024 / 1024 / 1024)|round(2) if item.file_size_bytes else '0' }} GB
                </div>
                
                <!-- The <video> tag intercepts the =dv stream and plays it natively -->
                <video controls preload="none">
                    <source src="{{ item.stream_url }}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                
                <div class="actions">
                    <a href="{{ item.stream_url }}" target="_blank">Raw Stream Link (=dv)</a>
                    <a href="{{ item.download_url }}" download>Download File (=d)</a>
                </div>
            </div>
        {% endfor %}
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    results = []
    
    if query:
        with db.Session() as session:
            # Case-insensitive search on the filename column
            stmt = select(MediaRecord).where(MediaRecord.filename.ilike(f"%{query}%")).limit(50)
            records = session.scalars(stmt).all()
            results = [db._to_media_model(r) for r in records]
            
    return render_template_string(HTML_TEMPLATE, query=query, results=results)

if __name__ == "__main__":
    app.run(debug=True, port=5000)