import uuid
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from app.services import ffmpeg_service, db_service, log_service
from app.services.ffmpeg_service import FFmpegError
video_bp = Blueprint("video", __name__)
def _allowed_file(filename):
    ext = Path(filename).suffix.lower()
    return ext in current_app.config["ALLOWED_VIDEO_EXTENSIONS"]
def _thumbnail_path_for(filename):
    stem = Path(filename).stem
    return Path(current_app.config["CACHE_FOLDER"]) / f"{stem}_thumb.jpg"
@video_bp.route("", methods=["GET"])
def list_videos():
    videos_folder = current_app.config["VIDEOS_FOLDER"]
    files = ffmpeg_service.list_video_files(videos_folder)
    results = []
    for file_path in files:
        filename = Path(file_path).name
        thumb_path = _thumbnail_path_for(filename)
        try:
            if not thumb_path.exists():
                meta = ffmpeg_service.probe(file_path)
                mid_point = min(1.0, meta["duration"] / 2) if meta["duration"] else 1.0
                ffmpeg_service.generate_thumbnail(file_path, thumb_path, timestamp=mid_point)
            else:
                meta = ffmpeg_service.probe(file_path)
        except FFmpegError as e:
            results.append({
                "filename": filename,
                "error": str(e),
                "thumbnail_url": None,
            })
            continue
        try:
            doc = db_service.upsert_source_video({
                "filename": filename,
                "duration": meta["duration"],
                "width": meta["width"],
                "height": meta["height"],
                "fps": meta["fps"],
                "codec": meta["codec"],
                "size_bytes": meta["size_bytes"],
                "has_audio": meta["has_audio"],
            })
        except Exception:
            doc = None
        results.append({
            "id": str(doc["_id"]) if doc else None,
            "filename": filename,
            "duration": meta["duration"],
            "width": meta["width"],
            "height": meta["height"],
            "fps": meta["fps"],
            "codec": meta["codec"],
            "size_bytes": meta["size_bytes"],
            "has_audio": meta["has_audio"],
            "video_url": f"/api/videos/stream/{filename}",
            "thumbnail_url": f"/api/videos/thumbnail/{filename}",
        })
    return jsonify({"videos": results, "folder": videos_folder})
@video_bp.route("/upload", methods=["POST"])
def upload_videos():
    videos_folder = current_app.config["VIDEOS_FOLDER"]
    files = request.files.getlist("files") or request.files.getlist("file")
    if not files:
        return jsonify({"error": "No files provided. Attach under form field 'files'."}), 400
    saved, skipped = [], []
    for f in files:
        if not f.filename:
            continue
        if not _allowed_file(f.filename):
            skipped.append({"filename": f.filename, "reason": "unsupported extension"})
            continue
        filename = secure_filename(f.filename)
        dest_path = Path(videos_folder) / filename
        if dest_path.exists():
            stem, ext = Path(filename).stem, Path(filename).suffix
            filename = f"{stem}_{uuid.uuid4().hex[:6]}{ext}"
            dest_path = Path(videos_folder) / filename
        f.save(str(dest_path))
        saved.append(filename)
    log_service.log_frontend(f"Uploaded {len(saved)} video(s), skipped {len(skipped)}", source="video")
    return jsonify({"saved": saved, "skipped": skipped})
@video_bp.route("/stream/<path:filename>", methods=["GET"])
def stream_video(filename):
    videos_folder = current_app.config["VIDEOS_FOLDER"]
    return send_from_directory(videos_folder, filename, conditional=True)
@video_bp.route("/thumbnail/<path:filename>", methods=["GET"])
def thumbnail(filename):
    cache_folder = current_app.config["CACHE_FOLDER"]
    stem = Path(filename).stem
    thumb_name = f"{stem}_thumb.jpg"
    if not (Path(cache_folder) / thumb_name).exists():
        return jsonify({"error": "Thumbnail not generated yet"}), 404
    return send_from_directory(cache_folder, thumb_name)
@video_bp.route("/proxy/<path:filename>", methods=["GET"])
def proxy_video(filename):
    videos_folder = current_app.config["VIDEOS_FOLDER"]
    cache_folder = current_app.config["CACHE_FOLDER"]
    src_path = Path(videos_folder) / filename
    if not src_path.exists():
        return jsonify({"error": "Source not found"}), 404
    stem = Path(filename).stem
    proxy_name = f"{stem}_proxy.mp4"
    proxy_path = Path(cache_folder) / proxy_name
    if not proxy_path.exists():
        try:
            ffmpeg_service.generate_preview_proxy(
                src_path, proxy_path,
                on_log=lambda msg: log_service.log_frontend(msg, source="video"),
            )
        except FFmpegError as e:
            return jsonify({"error": str(e), "stderr": e.stderr}), 500
    return send_from_directory(cache_folder, proxy_name, conditional=True)
@video_bp.route("/<path:filename>", methods=["DELETE"])
def delete_video(filename):
    videos_folder = current_app.config["VIDEOS_FOLDER"]
    safe_name = secure_filename(filename)
    file_path = Path(videos_folder) / safe_name
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404
    file_path.unlink()
    db_service.delete_source_video(safe_name)
    cache_folder = Path(current_app.config["CACHE_FOLDER"])
    stem = Path(safe_name).stem
    for suffix in ("_thumb.jpg", "_proxy.mp4"):
        cached = cache_folder / f"{stem}{suffix}"
        if cached.exists():
            cached.unlink()
    log_service.log_frontend(f"Deleted source video {safe_name}", source="video")
    return jsonify({"deleted": safe_name})