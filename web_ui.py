from flask import Flask, render_template, request, jsonify, Response
from sqlalchemy import select
from database import Database, MediaRecord

app = Flask(__name__)
db = Database()

def format_size(bytes_size):
    if not bytes_size:
        return "0 MB"
    mb = bytes_size / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.2f} MB"

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/vlc/<media_id>.m3u")
def vlc_playlist(media_id):
    with db.LocalSession() as session:
        record = session.get(MediaRecord, media_id)
        if not record or not record.stream_url:
            return "Media or stream not found", 404
        
        # Inject VLC-specific configuration to buffer 10,000ms (10 seconds) of video
        m3u_content = (
            "#EXTM3U\n"
            "#EXTVLCOPT:network-caching=10000\n"
            f"#EXTINF:-1,{record.filename}\n"
            f"{record.stream_url}"
        )
        
        response = Response(m3u_content, mimetype='audio/x-mpegurl')
        response.headers['Content-Disposition'] = f'attachment; filename="{record.filename}.m3u"'
        return response

@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    
    with db.LocalSession() as session:
        stmt = select(MediaRecord)
        if query:
            stmt = stmt.where(MediaRecord.filename.ilike(f"%{query}%"))
            
        stmt = stmt.order_by(MediaRecord.indexed_at.desc()).limit(20)
        records = session.scalars(stmt).all()
        
        results = []
        for r in records:
            model = db._to_media_model(r)
            
            web_stream_url = ""
            hi_res_cover = ""
            
            if model.preview_url:
                base_url = model.preview_url.split('=')[0]
                web_stream_url = f"{base_url}=m37"
                hi_res_cover = f"{base_url}=w1920-h1080"
            
            results.append({
                "media_id": model.media_id, # Added media_id for the VLC route
                "filename": model.filename or "Unknown Filename",
                "formatted_size": format_size(model.file_size_bytes),
                "stream_url": model.stream_url or "",
                "download_url": model.download_url or "",
                "web_stream_url": web_stream_url,
                "hi_res_cover": hi_res_cover
            })
            
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True, port=5000)