import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(val, default=False):
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), True)
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    VIDEOS_FOLDER = str((BASE_DIR / os.getenv("VIDEOS_FOLDER", "app/videos")).resolve())
    OUTPUTS_FOLDER = str((BASE_DIR / os.getenv("OUTPUTS_FOLDER", "app/outputs")).resolve())
    CACHE_FOLDER = str((BASE_DIR / os.getenv("CACHE_FOLDER", "app/cache")).resolve())
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024 * 5
    ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "snapify_editor")
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
    CLOUDINARY_BASE_FOLDER = os.getenv("CLOUDINARY_BASE_FOLDER", "snapify-editor")
    CLOUDINARY_VIDEOS_SUBFOLDER = os.getenv("CLOUDINARY_VIDEOS_SUBFOLDER", "videos")

    @property
    def CLOUDINARY_FULL_FOLDER(self):
        return f"{self.CLOUDINARY_BASE_FOLDER}/{self.CLOUDINARY_VIDEOS_SUBFOLDER}"

    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "https://ollama.com")
    OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    YOUTUBE_CLIENT_SECRETS_FILE = str(BASE_DIR / os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secret.json"))
    YOUTUBE_TOKEN_FILE = str(BASE_DIR / os.getenv("YOUTUBE_TOKEN_FILE", "youtube_token.json"))
    YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI", "http://localhost:5000/youtube/oauth2callback")
    YOUTUBE_SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
    ]
    SCHEDULER_POLL_INTERVAL = int(os.getenv("SCHEDULER_POLL_INTERVAL", "60"))

    @classmethod
    def ensure_dirs(cls):
        for folder in (cls.VIDEOS_FOLDER, cls.OUTPUTS_FOLDER, cls.CACHE_FOLDER):
            Path(folder).mkdir(parents=True, exist_ok=True)
