from flask import Blueprint, current_app, jsonify

from app.services import db_service, cloudinary_service, ollama_service, youtube_service

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    mongo_ok, mongo_msg = db_service.check_connection()
    ollama_ok, ollama_msg = ollama_service.check_connection(current_app.config)
    youtube_ok, youtube_msg = youtube_service.check_connection(current_app.config)
    return jsonify({
        "ffmpeg": {"ok": True},
        "mongo": {"ok": mongo_ok, "message": mongo_msg},
        "cloudinary": {"ok": cloudinary_service.is_configured(), "message": "configured" if cloudinary_service.is_configured() else "not configured"},
        "ollama": {"ok": ollama_ok, "message": ollama_msg},
        "youtube": {"ok": youtube_ok, "message": youtube_msg},
    })
