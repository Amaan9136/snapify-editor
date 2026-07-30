import logging
import os

from dotenv import load_dotenv
from flask import Flask

load_dotenv()

from app.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.ensure_dirs()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    for noisy_logger in ("pymongo", "watchdog", "urllib3", "googleapiclient", "google_auth_httplib2"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    from app.services import db_service, cloudinary_service, scheduler_service

    try:
        db_service.init_db(app)
        app.logger.info("MongoDB initialized (%s)", app.config["MONGO_DB_NAME"])
    except Exception as e:
        app.logger.warning("MongoDB init failed - app will run but DB features will error: %s", e)

    cloudinary_service.init_cloudinary(app)
    if cloudinary_service.is_configured():
        app.logger.info("Cloudinary configured")
    else:
        app.logger.warning("Cloudinary not configured - set CLOUDINARY_* in .env to enable uploads")

    from app.routes.main_routes import main_bp
    from app.routes.video_routes import video_bp
    from app.routes.editor_routes import editor_bp
    from app.routes.youtube_routes import youtube_bp
    from app.routes.ollama_routes import ollama_bp
    from app.routes.health_routes import health_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(video_bp, url_prefix="/api/videos")
    app.register_blueprint(editor_bp, url_prefix="/api/editor")
    app.register_blueprint(youtube_bp, url_prefix="/youtube")
    app.register_blueprint(ollama_bp, url_prefix="/api/ollama")
    app.register_blueprint(health_bp, url_prefix="/api")

    if not app.config["DEBUG"] or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        scheduler_service.start_scheduler(app)

    return app
