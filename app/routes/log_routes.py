from flask import Blueprint, Response
from app.services import log_service
log_bp = Blueprint("logs", __name__)
@log_bp.route("/stream", methods=["GET"])
def stream():
    q = log_service.subscribe()
    def generate():
        try:
            for chunk in log_service.stream_events(q):
                yield chunk
        finally:
            log_service.unsubscribe(q)
    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })