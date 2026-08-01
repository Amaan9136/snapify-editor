import logging
import threading
from app.services import db_service, youtube_service, cloudinary_service
logger = logging.getLogger("snapify.scheduler")
_stop_event = threading.Event()
_thread = None
def _process_job(app, job):
    job_id = str(job["_id"])
    db_service.update_upload_job(job_id, {"status": "uploading"})
    logger.info("Processing upload job %s for clip %s", job_id, job.get("clip_id"))
    try:
        clip = db_service.get_clip(job["clip_id"])
        if not clip:
            raise RuntimeError(f"Clip {job['clip_id']} not found")
        local_path = clip.get("local_path")
        if not local_path:
            raise RuntimeError("Clip has no local_path to upload")
        result = youtube_service.upload_video(
            app.config,
            video_path=local_path,
            title=job.get("title") or clip.get("title") or "Untitled Short",
            description=job.get("description", ""),
            tags=job.get("hashtags", []),
            privacy_status=job.get("privacy_status", "private"),
            publish_at=job.get("publish_at_iso"),
        )
        db_service.update_upload_job(job_id, {
            "status": "done",
            "youtube_video_id": result["video_id"],
            "youtube_url": result["url"],
        })
        db_service.update_clip(job["clip_id"], {
            "status": "published_youtube",
            "youtube_video_id": result["video_id"],
            "youtube_url": result["url"],
        })
        logger.info("Upload job %s succeeded -> %s", job_id, result["url"])
    except Exception as e:
        logger.exception("Upload job %s failed", job_id)
        db_service.update_upload_job(job_id, {"status": "failed", "error": str(e)})
def _poll_loop(app):
    interval = app.config.get("SCHEDULER_POLL_INTERVAL", 60)
    logger.info("Scheduler thread started, polling every %ss", interval)
    while not _stop_event.is_set():
        try:
            with app.app_context():
                due_jobs = db_service.get_due_upload_jobs()
                for job in due_jobs:
                    _process_job(app, job)
        except Exception:
            logger.exception("Scheduler poll cycle failed")
        _stop_event.wait(interval)
def start_scheduler(app):
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_poll_loop, args=(app,), daemon=True, name="snapify-scheduler")
    _thread.start()
def stop_scheduler():
    _stop_event.set()