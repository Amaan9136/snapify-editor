import uuid
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_from_directory
from app.services import ffmpeg_service, db_service, cloudinary_service, log_service
from app.services.ffmpeg_service import FFmpegError
editor_bp = Blueprint("editor", __name__)
def _source_path(filename):
    return Path(current_app.config["VIDEOS_FOLDER"]) / filename
def _validate_source(filename):
    path = _source_path(filename)
    if not path.exists():
        return None, (jsonify({"error": f"Source video '{filename}' not found in local /videos folder"}), 404)
    return path, None
@editor_bp.route("/probe", methods=["POST"])
def probe_video():
    body = request.get_json(force=True) or {}
    filename = body.get("filename")
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    path, err = _validate_source(filename)
    if err:
        return err
    try:
        meta = ffmpeg_service.probe(path)
    except FFmpegError as e:
        return jsonify({"error": str(e), "stderr": e.stderr}), 500
    meta["aspect_ratios_available"] = list(ffmpeg_service.ASPECT_RATIOS.keys()) + ["custom"]
    return jsonify(meta)
@editor_bp.route("/split", methods=["POST"])
def split_video():
    body = request.get_json(force=True) or {}
    filename = body.get("filename")
    split_points = body.get("split_points", [])
    if not filename:
        return jsonify({"error": "filename is required"}), 400
    if not isinstance(split_points, list) or not split_points:
        return jsonify({"error": "split_points must be a non-empty list of seconds"}), 400
    path, err = _validate_source(filename)
    if err:
        return err
    out_dir = Path(current_app.config["OUTPUTS_FOLDER"]) / "splits"
    try:
        segments = ffmpeg_service.split_video_at_points(path, split_points, out_dir, base_name=Path(filename).stem)
    except FFmpegError as e:
        return jsonify({"error": str(e), "stderr": e.stderr}), 500
    for seg in segments:
        seg["filename"] = Path(seg["path"]).name
        seg["preview_url"] = f"/api/editor/output/splits/{seg['filename']}"
        del seg["path"]
    return jsonify({"source": filename, "segments": segments})
def _parse_render_params(body):
    filename = body.get("filename")
    start = float(body.get("start", 0))
    end = float(body.get("end", 0))
    ratio_key = body.get("ratio", "9:16")
    custom_ratio = body.get("custom_ratio")
    volume = float(body.get("volume", 1.0))
    mute = bool(body.get("mute", False))
    speed = float(body.get("speed", 1.0))
    brightness = body.get("brightness")
    contrast = body.get("contrast")
    saturation = body.get("saturation")
    title = body.get("title", "")
    fit_pad = bool(body.get("fit_pad", True))
    custom_tuple = (custom_ratio["w"], custom_ratio["h"]) if custom_ratio else None
    return dict(
        filename=filename, start=start, end=end, ratio_key=ratio_key, custom_ratio=custom_tuple,
        volume=volume, mute=mute, speed=speed,
        brightness=brightness, contrast=contrast, saturation=saturation, title=title, fit_pad=fit_pad,
    )
def _render_one(params):
    filename = params["filename"]
    path, err = _validate_source(filename)
    if err:
        raise FFmpegError(f"Source video '{filename}' not found")
    out_name = f"{Path(filename).stem}_{params['ratio_key'].replace(':', 'x')}_{uuid.uuid4().hex[:8]}.mp4"
    out_dir = Path(current_app.config["OUTPUTS_FOLDER"]) / "renders"
    out_path = out_dir / out_name
    log_service.log_frontend(f"Rendering {filename} -> {out_name} ({params['ratio_key']})", source="editor", clip_key=out_name)
    render_result = ffmpeg_service.render_reel(
        path, out_path,
        start=params["start"], end=params["end"],
        ratio_key=params["ratio_key"], custom_ratio=params["custom_ratio"],
        volume=params["volume"], mute=params["mute"], speed=params["speed"],
        brightness=params["brightness"], contrast=params["contrast"], saturation=params["saturation"],
        fit_pad=params["fit_pad"],
        on_log=lambda msg: log_service.log_frontend(msg, source="editor", clip_key=out_name),
        on_progress=lambda pct: log_service.log_frontend(f"Encoding {out_name}: {pct*100:.0f}%", source="editor", progress=pct, clip_key=out_name),
    )
    clip_id = None
    try:
        source_doc = db_service.get_source_video_by_filename(filename)
        clip_doc = db_service.insert_clip({
            "source_filename": filename,
            "source_video_id": str(source_doc["_id"]) if source_doc else None,
            "local_path": str(out_path),
            "filename": out_name,
            "title": params.get("title") or Path(filename).stem,
            "start": params["start"],
            "end": params["end"],
            "ratio": params["ratio_key"],
            "fit_pad": params["fit_pad"],
            "width": render_result["width"],
            "height": render_result["height"],
            "duration": render_result["duration"],
            "status": "rendered",
        })
        clip_id = str(clip_doc["_id"])
    except Exception:
        pass
    log_service.log_frontend(f"Render complete: {out_name}", source="editor", progress=1.0, clip_key=out_name)
    return {
        "clip_id": clip_id,
        "filename": out_name,
        "preview_url": f"/api/editor/output/renders/{out_name}",
        "width": render_result["width"],
        "height": render_result["height"],
        "duration": render_result["duration"],
    }
@editor_bp.route("/render", methods=["POST"])
def render_video():
    body = request.get_json(force=True) or {}
    if not body.get("filename"):
        return jsonify({"error": "filename is required"}), 400
    params = _parse_render_params(body)
    try:
        result = _render_one(params)
    except FFmpegError as e:
        return jsonify({"error": str(e), "stderr": getattr(e, "stderr", "")}), 500
    return jsonify(result)
@editor_bp.route("/render-batch", methods=["POST"])
def render_batch():
    body = request.get_json(force=True) or {}
    clip_specs = body.get("clips", [])
    if not isinstance(clip_specs, list) or not clip_specs:
        return jsonify({"error": "clips must be a non-empty list of render specs"}), 400
    results = []
    for i, spec in enumerate(clip_specs):
        if not spec.get("filename"):
            results.append({"index": i, "error": "filename is required"})
            continue
        try:
            params = _parse_render_params(spec)
            result = _render_one(params)
            result["index"] = i
            results.append(result)
        except FFmpegError as e:
            results.append({"index": i, "error": str(e), "stderr": getattr(e, "stderr", "")})
    return jsonify({"results": results})
@editor_bp.route("/upload-cloudinary", methods=["POST"])
def upload_to_cloudinary():
    body = request.get_json(force=True) or {}
    clip_id = body.get("clip_id")
    if not clip_id:
        return jsonify({"error": "clip_id is required"}), 400
    clip = db_service.get_clip(clip_id)
    if not clip:
        return jsonify({"error": "Clip not found"}), 404
    if not cloudinary_service.is_configured():
        return jsonify({"error": "Cloudinary is not configured. Set CLOUDINARY_* in .env."}), 400
    try:
        result = cloudinary_service.upload_video(
            clip["local_path"],
            public_id=Path(clip["filename"]).stem,
            app_config=current_app.config,
        )
    except Exception as e:
        return jsonify({"error": f"Cloudinary upload failed: {e}"}), 500
    db_service.update_clip(clip_id, {
        "status": "uploaded_cloudinary",
        "cloudinary_public_id": result["public_id"],
        "cloudinary_url": result["secure_url"],
    })
    log_service.log_frontend(f"Uploaded clip {clip_id} to Cloudinary", source="editor")
    return jsonify({
        "clip_id": clip_id,
        "cloudinary_url": result["secure_url"],
        "cloudinary_public_id": result["public_id"],
    })
@editor_bp.route("/clips", methods=["GET"])
def list_clips():
    try:
        clips = db_service.list_clips()
    except Exception:
        return jsonify({"clips": [], "error": "Could not reach the database"})
    for c in clips:
        c["_id"] = str(c["_id"])
        if c.get("filename"):
            c["preview_url"] = f"/api/editor/output/renders/{c['filename']}"
    return jsonify({"clips": clips})
@editor_bp.route("/clips/<clip_id>", methods=["DELETE"])
def delete_clip(clip_id):
    clip = db_service.get_clip(clip_id)
    if not clip:
        return jsonify({"error": "Clip not found"}), 404
    if clip.get("local_path"):
        local_path = Path(clip["local_path"])
        if local_path.exists():
            local_path.unlink()
    cloudinary_error = None
    if clip.get("cloudinary_public_id"):
        try:
            cloudinary_service.delete_video(clip["cloudinary_public_id"])
        except Exception as e:
            cloudinary_error = str(e)
    db_service.delete_clip(clip_id)
    log_service.log_frontend(f"Deleted clip {clip_id}", source="editor")
    result = {"deleted": clip_id}
    if cloudinary_error:
        result["cloudinary_warning"] = f"Local/DB deleted, but Cloudinary cleanup failed: {cloudinary_error}"
    return jsonify(result)
@editor_bp.route("/output/<path:subpath>", methods=["GET"])
def serve_output(subpath):
    outputs_folder = current_app.config["OUTPUTS_FOLDER"]
    full_path = Path(outputs_folder) / subpath
    if not full_path.exists():
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(str(full_path.parent), full_path.name, conditional=True)