from flask import Blueprint, current_app, jsonify, request

from app.services import ollama_service, db_service
from app.services.ollama_service import OllamaError

ollama_bp = Blueprint("ollama", __name__)


@ollama_bp.route("/generate", methods=["POST"])
def generate_metadata():
    body = request.get_json(force=True) or {}
    clip_id = body.get("clip_id")
    context = body.get("context", "")
    notes = body.get("notes")
    if not clip_id:
        return jsonify({"error": "clip_id is required"}), 400
    clip = db_service.get_clip(clip_id)
    if not clip:
        return jsonify({"error": "Clip not found"}), 404
    if not context:
        context = (
            f"Filename: {clip.get('source_filename')}, "
            f"trimmed {clip.get('start')}s-{clip.get('end')}s, "
            f"aspect ratio {clip.get('ratio')}, duration {clip.get('duration')}s."
        )
    try:
        result = ollama_service.generate_metadata(current_app.config, context, notes)
    except OllamaError as e:
        return jsonify({"error": str(e)}), 502
    saved = db_service.save_caption_set(
        clip_id, result["title"], result["description"], result["hashtags"], result["raw"]
    )
    saved["_id"] = str(saved["_id"])
    return jsonify(saved)


@ollama_bp.route("/status", methods=["GET"])
def status():
    ok, message = ollama_service.check_connection(current_app.config)
    return jsonify({"connected": ok, "message": message, "model": current_app.config["OLLAMA_MODEL"]})
