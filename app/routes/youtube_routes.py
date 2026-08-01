from datetime import datetime, timezone
from flask import Blueprint, current_app, jsonify, redirect, request, session
from app.services import youtube_service, db_service, log_service
from app.services.youtube_service import YouTubeAuthError, YouTubeUploadError
youtube_bp = Blueprint("youtube", __name__)
@youtube_bp.route("/authorize", methods=["GET"])
def authorize():
    try:
        auth_url, state = youtube_service.get_authorization_url(current_app.config)
    except YouTubeAuthError as e:
        return jsonify({"error": str(e)}), 400
    session["youtube_oauth_state"] = state
    return redirect(auth_url)
@youtube_bp.route("/oauth2callback", methods=["GET"])
def oauth2callback():
    state = session.get("youtube_oauth_state")
    try:
        youtube_service.exchange_code_for_token(current_app.config, request.url, state=state)
    except YouTubeAuthError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"OAuth exchange failed: {e}"}), 400
    return """
    <html><body style="font-family: sans-serif; text-align:center; padding-top: 80px;">
    <h2>&#9989; YouTube connected successfully!</h2>
    <p>You can close this tab and return to Snapify Editor.</p>
    <script>setTimeout(() => window.close(), 2000);</script>
    </body></html>
    """
@youtube_bp.route("/status", methods=["GET"])
def status():
    ok, message = youtube_service.check_connection(current_app.config)
    return jsonify({"authorized": ok, "message": message})
@youtube_bp.route("/upload-now", methods=["POST"])
def upload_now():
    body = request.get_json(force=True) or {}
    clip_id = body.get("clip_id")
    if not clip_id:
        return jsonify({"error": "clip_id is required"}), 400
    clip = db_service.get_clip(clip_id)
    if not clip:
        return jsonify({"error": "Clip not found"}), 404
    title = body.get("title") or clip.get("title") or "Untitled Short"
    description = body.get("description", "")
    hashtags = body.get("hashtags", [])
    description_with_tags = f"{description}\n\n{' '.join(hashtags)}".strip()
    try:
        result = youtube_service.upload_video(
            current_app.config,
            video_path=clip["local_path"],
            title=title,
            description=description_with_tags,
            tags=[h.lstrip("#") for h in hashtags],
            privacy_status=body.get("privacy_status", "private"),
        )
    except (YouTubeAuthError, YouTubeUploadError) as e:
        return jsonify({"error": str(e)}), 400
    db_service.update_clip(clip_id, {
        "status": "published_youtube",
        "youtube_video_id": result["video_id"],
        "youtube_url": result["url"],
    })
    log_service.log_frontend(f"Published clip {clip_id} to YouTube: {result['url']}", source="youtube")
    return jsonify(result)
@youtube_bp.route("/schedule", methods=["POST"])
def schedule_upload():
    body = request.get_json(force=True) or {}
    clip_id = body.get("clip_id")
    scheduled_for_str = body.get("scheduled_for")
    if not clip_id:
        return jsonify({"error": "clip_id is required"}), 400
    if not scheduled_for_str:
        return jsonify({"error": "scheduled_for (ISO datetime) is required"}), 400
    clip = db_service.get_clip(clip_id)
    if not clip:
        return jsonify({"error": "Clip not found"}), 404
    try:
        scheduled_for = datetime.fromisoformat(scheduled_for_str.replace("Z", "+00:00"))
        if scheduled_for.tzinfo is None:
            scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
    except ValueError:
        return jsonify({"error": "scheduled_for must be a valid ISO-8601 datetime"}), 400
    publish_at_iso = body.get("publish_at") or scheduled_for_str
    job = db_service.create_upload_job({
        "clip_id": clip_id,
        "title": body.get("title") or clip.get("title"),
        "description": body.get("description", ""),
        "hashtags": body.get("hashtags", []),
        "privacy_status": body.get("privacy_status", "private"),
        "scheduled_for": scheduled_for,
        "publish_at_iso": publish_at_iso,
    })
    job["_id"] = str(job["_id"])
    job["scheduled_for"] = job["scheduled_for"].isoformat()
    log_service.log_frontend(f"Scheduled clip {clip_id} for {job['scheduled_for']}", source="youtube")
    return jsonify(job)
@youtube_bp.route("/jobs", methods=["GET"])
def list_jobs():
    jobs = db_service.list_upload_jobs()
    for j in jobs:
        j["_id"] = str(j["_id"])
        if j.get("scheduled_for"):
            j["scheduled_for"] = j["scheduled_for"].isoformat()
    return jsonify({"jobs": jobs})