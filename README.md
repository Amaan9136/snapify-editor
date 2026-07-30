# Snapify Editor

Local-first reel/shorts editor. Flask + vanilla JS frontend, FFmpeg for all video work, MongoDB for metadata, Cloudinary for hosting finished clips, Ollama for captions/hashtags, YouTube Data API for publishing.

Source videos stay on disk in `app/videos` for editing speed — only finished, rendered clips get pushed to Cloudinary.

## Requirements
- Python 3.10+
- `ffmpeg` and `ffprobe` on PATH
- MongoDB running (local `mongod` or Atlas)
- Cloudinary account (for clip hosting)
- Ollama account/host (for captions) — see below
- Google Cloud project (for YouTube upload) — see `SETUP_YOUTUBE.md`

## Setup
```bash
git clone <this repo> snapify-editor
cd snapify-editor
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Edit `.env`:
- `MONGO_URI` — defaults to `mongodb://localhost:27017`, start `mongod` before running the app.
- `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` — from your [Cloudinary dashboard](https://console.cloudinary.com/console).
- `OLLAMA_HOST` / `OLLAMA_API_KEY` / `OLLAMA_MODEL` — see below.
- YouTube vars — see `SETUP_YOUTUBE.md`.

Run:
```bash
python3 app.py
```
Open `http://localhost:5000`.

## Ollama
`OLLAMA_HOST=https://ollama.com` with an API key (from `https://ollama.com/settings/keys`) uses Ollama's cloud models — no local GPU needed. To run fully local instead, set `OLLAMA_HOST=http://localhost:11434`, drop the API key, and `ollama pull gpt-oss:20b-cloud` first. Either way the app talks to the same `/api/chat` endpoint, so no code changes are needed to switch.

## Using it
1. **Library** — drag & drop videos in, or use "Add videos". They're copied straight into `app/videos`.
2. **Editor** — pick a source, drag the timeline handles to trim, drag the crop box on the preview to set pan start/end, pick an aspect ratio (or Custom), adjust speed/brightness/contrast/saturation/volume. Everything previews live via CSS — no server round-trip until you render.
3. Click **Add split marker** while scrubbing to mark split points, then **Split at markers** to cut the source into separate files (written to `app/outputs/splits`).
4. **Add this clip to render queue** to stage a clip, repeat for as many clips as you want from the same or different sources, then **Render queue** to export them all in one batch (this is what actually runs ffmpeg and applies your trim/crop/pan/effects).
5. **Rendered Clips** tab — push a clip to Cloudinary, or **Publish to YouTube** to open the publish modal: generate a title/description/hashtags with Ollama, then publish immediately or schedule it.
6. **Publish** tab — see all scheduled/completed YouTube upload jobs and their status.

## How scheduling works
Scheduling a clip writes a job to MongoDB's `upload_jobs` collection. A background thread inside the Flask process polls that collection every `SCHEDULER_POLL_INTERVAL` seconds (default 60) and uploads any due job. This is fine for a single-instance local app; for multi-worker production use, swap it for Celery beat + a real broker (see `app/services/scheduler_service.py`).

YouTube itself also supports true scheduled publishing (`privacyStatus: private` + `publishAt`) — the app sets this automatically so the video goes public at the right time even if it was uploaded earlier.

## Project layout
```
app/
  config.py            env-driven settings
  services/
    ffmpeg_service.py  probe, trim, split, crop/pan, render — the core engine
    db_service.py       MongoDB access
    cloudinary_service.py
    ollama_service.py
    youtube_service.py  OAuth + upload
    scheduler_service.py background upload poller
  routes/              Flask blueprints (videos, editor, youtube, ollama, health)
  static/js/           vanilla JS: api.js, library.js, editor.js, clips.js, publish.js, app.js
  static/css/main.css
  templates/index.html
  videos/              your source videos (git-ignored)
  outputs/             rendered clips + splits (git-ignored)
  cache/               thumbnails + preview proxies (git-ignored)
app.py
```

## Notes
- Uploads accept `.mp4 .mov .mkv .avi .webm .m4v` up to 5GB (`MAX_CONTENT_LENGTH` in `app/config.py`).
- If MongoDB isn't reachable, the app still starts and serves the editor; video listing, rendering, and clip history degrade gracefully (renders still complete and save to disk, just without a database record) rather than failing outright — get MongoDB running to get full history/publishing back.
- `/api/health` shows live status for Mongo, Cloudinary, Ollama, and YouTube auth — check it first if something's not working.
