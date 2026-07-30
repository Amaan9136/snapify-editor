from datetime import datetime, timezone

from pymongo import MongoClient, ASCENDING, DESCENDING

_client = None
_db = None


def init_db(app):
    global _client, _db
    uri = app.config["MONGO_URI"]
    db_name = app.config["MONGO_DB_NAME"]
    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    _db = _client[db_name]
    _db.source_videos.create_index([("filename", ASCENDING)], unique=True)
    _db.clips.create_index([("created_at", DESCENDING)])
    _db.clips.create_index([("source_video_id", ASCENDING)])
    _db.upload_jobs.create_index([("scheduled_for", ASCENDING)])
    _db.upload_jobs.create_index([("status", ASCENDING)])
    _db.captions.create_index([("clip_id", ASCENDING)])
    return _db


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized - call init_db(app) at startup first.")
    return _db


def check_connection():
    try:
        _client.admin.command("ping")
        return True, "connected"
    except Exception as e:
        return False, str(e)


def now():
    return datetime.now(timezone.utc)


def upsert_source_video(doc):
    db = get_db()
    doc = dict(doc)
    doc["updated_at"] = now()
    result = db.source_videos.find_one_and_update(
        {"filename": doc["filename"]},
        {"$set": doc, "$setOnInsert": {"created_at": now()}},
        upsert=True,
        return_document=True,
    )
    return result


def list_source_videos():
    db = get_db()
    return list(db.source_videos.find().sort("created_at", DESCENDING))


def get_source_video(video_id):
    from bson import ObjectId
    db = get_db()
    return db.source_videos.find_one({"_id": ObjectId(video_id)})


def get_source_video_by_filename(filename):
    db = get_db()
    return db.source_videos.find_one({"filename": filename})


def delete_source_video(filename):
    db = get_db()
    return db.source_videos.delete_one({"filename": filename})


def insert_clip(doc):
    db = get_db()
    doc = dict(doc)
    doc.setdefault("created_at", now())
    doc.setdefault("status", "rendered")
    result = db.clips.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def update_clip(clip_id, updates):
    from bson import ObjectId
    db = get_db()
    updates = dict(updates)
    updates["updated_at"] = now()
    db.clips.update_one({"_id": ObjectId(clip_id)}, {"$set": updates})
    return db.clips.find_one({"_id": ObjectId(clip_id)})


def get_clip(clip_id):
    from bson import ObjectId
    db = get_db()
    return db.clips.find_one({"_id": ObjectId(clip_id)})


def list_clips(limit=100):
    db = get_db()
    return list(db.clips.find().sort("created_at", DESCENDING).limit(limit))


def save_caption_set(clip_id, title, description, hashtags, raw_model_output=None):
    db = get_db()
    doc = {
        "clip_id": clip_id,
        "title": title,
        "description": description,
        "hashtags": hashtags,
        "raw_model_output": raw_model_output,
        "created_at": now(),
    }
    result = db.captions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def get_latest_caption_for_clip(clip_id):
    db = get_db()
    return db.captions.find_one({"clip_id": clip_id}, sort=[("created_at", DESCENDING)])


def create_upload_job(doc):
    db = get_db()
    doc = dict(doc)
    doc.setdefault("status", "scheduled")
    doc.setdefault("created_at", now())
    result = db.upload_jobs.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def update_upload_job(job_id, updates):
    from bson import ObjectId
    db = get_db()
    updates = dict(updates)
    updates["updated_at"] = now()
    db.upload_jobs.update_one({"_id": ObjectId(job_id)}, {"$set": updates})
    return db.upload_jobs.find_one({"_id": ObjectId(job_id)})


def get_due_upload_jobs():
    db = get_db()
    return list(db.upload_jobs.find({
        "status": "scheduled",
        "$or": [{"scheduled_for": None}, {"scheduled_for": {"$lte": now()}}],
    }))


def list_upload_jobs(limit=100):
    db = get_db()
    return list(db.upload_jobs.find().sort("created_at", DESCENDING).limit(limit))
