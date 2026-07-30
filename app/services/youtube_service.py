import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError


class YouTubeAuthError(RuntimeError):
    pass


class YouTubeUploadError(RuntimeError):
    pass


def _client_secrets_exist(app_config):
    return Path(app_config["YOUTUBE_CLIENT_SECRETS_FILE"]).exists()


def build_auth_flow(app_config):
    if not _client_secrets_exist(app_config):
        raise YouTubeAuthError(
            f"Missing client secrets file at {app_config['YOUTUBE_CLIENT_SECRETS_FILE']}. "
            "See SETUP_YOUTUBE.md to create one in Google Cloud Console."
        )
    flow = Flow.from_client_secrets_file(
        app_config["YOUTUBE_CLIENT_SECRETS_FILE"],
        scopes=app_config["YOUTUBE_SCOPES"],
        redirect_uri=app_config["YOUTUBE_REDIRECT_URI"],
    )
    return flow


def get_authorization_url(app_config):
    flow = build_auth_flow(app_config)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def exchange_code_for_token(app_config, authorization_response_url, state=None):
    flow = build_auth_flow(app_config)
    if state:
        flow.state = state
    flow.fetch_token(authorization_response=authorization_response_url)
    creds = flow.credentials
    _save_credentials(app_config, creds)
    return creds


def _save_credentials(app_config, creds):
    Path(app_config["YOUTUBE_TOKEN_FILE"]).write_text(creds.to_json())


def load_credentials(app_config):
    token_path = Path(app_config["YOUTUBE_TOKEN_FILE"])
    if not token_path.exists():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path), app_config["YOUTUBE_SCOPES"])
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_credentials(app_config, creds)
    return creds


def is_authorized(app_config):
    try:
        creds = load_credentials(app_config)
        return creds is not None and creds.valid
    except Exception:
        return False


def _get_youtube_client(app_config):
    creds = load_credentials(app_config)
    if not creds:
        raise YouTubeAuthError("Not authorized with YouTube yet. Visit /youtube/authorize first.")
    return build("youtube", "v3", credentials=creds)


def upload_video(app_config, video_path, title, description, tags=None,
                  category_id="22", privacy_status="private", publish_at=None,
                  made_for_kids=False, progress_callback=None):
    if not os.path.exists(video_path):
        raise YouTubeUploadError(f"File not found: {video_path}")
    youtube = _get_youtube_client(app_config)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }
    if publish_at:
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at
    media = MediaFileUpload(video_path, chunksize=1024 * 1024 * 4, resumable=True, mimetype="video/*")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    try:
        while response is None:
            status, response = request.next_chunk()
            if status and progress_callback:
                progress_callback(status.resumable_progress, status.total_size)
    except HttpError as e:
        raise YouTubeUploadError(f"YouTube upload failed: {e}") from e
    video_id = response.get("id")
    return {"video_id": video_id, "url": f"https://youtube.com/watch?v={video_id}", "raw": response}


def check_connection(app_config):
    if not _client_secrets_exist(app_config):
        return False, "client_secret.json not found - see SETUP_YOUTUBE.md"
    if not is_authorized(app_config):
        return False, "Not authorized yet - visit /youtube/authorize"
    return True, "authorized"
