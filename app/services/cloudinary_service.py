import cloudinary
import cloudinary.uploader
import cloudinary.api

_configured = False


def init_cloudinary(app):
    global _configured
    cloudinary.config(
        cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=app.config["CLOUDINARY_API_KEY"],
        api_secret=app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )
    _configured = bool(app.config["CLOUDINARY_CLOUD_NAME"] and app.config["CLOUDINARY_API_KEY"])


def is_configured():
    return _configured


def upload_video(local_path, public_id=None, folder=None, app_config=None):
    if not _configured:
        raise RuntimeError(
            "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME / "
            "CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET in your .env file."
        )
    folder = folder or (app_config.get("CLOUDINARY_FULL_FOLDER") if app_config else "snapify-editor/videos")
    kwargs = {
        "resource_type": "video",
        "folder": folder,
        "overwrite": True,
        "use_filename": True,
        "unique_filename": True,
    }
    if public_id:
        kwargs["public_id"] = public_id
    result = cloudinary.uploader.upload_large(local_path, **kwargs)
    return result


def delete_video(public_id):
    if not _configured:
        raise RuntimeError("Cloudinary is not configured.")
    return cloudinary.uploader.destroy(public_id, resource_type="video")
