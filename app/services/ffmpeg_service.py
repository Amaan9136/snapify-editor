import json
import shlex
import subprocess
import uuid
from pathlib import Path

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"

ASPECT_RATIOS = {
    "9:16": (9, 16),
    "16:9": (16, 9),
    "4:5": (4, 5),
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:4": (3, 4),
}


class FFmpegError(RuntimeError):
    def __init__(self, message, stderr="", cmd=None):
        super().__init__(message)
        self.stderr = stderr
        self.cmd = cmd


def _run(cmd, timeout=None):
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise FFmpegError(f"Binary not found: {cmd[0]}. Is ffmpeg/ffprobe installed and on PATH?") from e
    except subprocess.TimeoutExpired as e:
        raise FFmpegError(f"Command timed out after {timeout}s: {' '.join(shlex.quote(c) for c in cmd)}") from e
    if result.returncode != 0:
        stderr_text = result.stderr.decode("utf-8", errors="replace")
        raise FFmpegError(
            f"Command failed (exit {result.returncode}): {' '.join(shlex.quote(c) for c in cmd)}",
            stderr=stderr_text,
            cmd=cmd,
        )
    return result


def probe(path):
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = _run(cmd, timeout=30)
    data = json.loads(result.stdout.decode("utf-8", errors="replace"))
    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise FFmpegError(f"No video stream found in {path}")
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or video_stream.get("duration") or 0.0)
    fps = 0.0
    rate_str = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "0/1"
    try:
        num, den = rate_str.split("/")
        num, den = float(num), float(den)
        fps = round(num / den, 3) if den else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    rotation = 0
    tags = video_stream.get("tags", {}) or {}
    if "rotate" in tags:
        try:
            rotation = int(tags["rotate"])
        except ValueError:
            rotation = 0
    for sd in video_stream.get("side_data_list", []) or []:
        if "rotation" in sd:
            try:
                rotation = int(sd["rotation"])
            except (ValueError, TypeError):
                pass
    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    if abs(rotation) in (90, 270):
        width, height = height, width
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "codec": video_stream.get("codec_name", "unknown"),
        "size_bytes": int(fmt.get("size") or 0),
        "has_audio": audio_stream is not None,
        "rotation": rotation,
        "bit_rate": int(fmt.get("bit_rate") or 0),
    }


def generate_thumbnail(video_path, out_path, timestamp=1.0):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        FFMPEG_BIN, "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "3",
        str(out_path),
    ]
    _run(cmd, timeout=30)
    return out_path


def generate_preview_proxy(video_path, out_path, max_height=480):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    scale_filter = f"scale=-2:'min({max_height},ih)'"
    cmd = [
        FFMPEG_BIN, "-y",
        "-i", str(video_path),
        "-vf", scale_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run(cmd, timeout=600)
    return out_path


def _target_dims_for_ratio(src_w, src_h, ratio_key, custom_ratio=None):
    if ratio_key == "custom" and custom_ratio:
        rw, rh = custom_ratio
    else:
        rw, rh = ASPECT_RATIOS.get(ratio_key, (9, 16))
    target_ratio = rw / rh
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        crop_h = src_h
        crop_w = int(round(crop_h * target_ratio))
    else:
        crop_w = src_w
        crop_h = int(round(crop_w / target_ratio))
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    return crop_w, crop_h


def build_crop_pan_filter(src_w, src_h, ratio_key, custom_ratio=None,
                           pan_start=None, pan_end=None, duration=None):
    crop_w, crop_h = _target_dims_for_ratio(src_w, src_h, ratio_key, custom_ratio)
    max_x = max(src_w - crop_w, 0)
    max_y = max(src_h - crop_h, 0)
    if pan_start is None:
        pan_start = {"x": 0.5, "y": 0.5}
    if pan_end is None:
        pan_end = pan_start
    x0 = int(round(max(0, min(1, pan_start.get("x", 0.5))) * max_x))
    y0 = int(round(max(0, min(1, pan_start.get("y", 0.5))) * max_y))
    x1 = int(round(max(0, min(1, pan_end.get("x", 0.5))) * max_x))
    y1 = int(round(max(0, min(1, pan_end.get("y", 0.5))) * max_y))
    if (x0, y0) == (x1, y1) or not duration or duration <= 0:
        filter_str = f"crop={crop_w}:{crop_h}:{x0}:{y0}"
    else:
        expr_progress = f"min(t/{duration},1)"
        x_expr = f"{x0}+({x1}-{x0})*{expr_progress}"
        y_expr = f"{y0}+({y1}-{y0})*{expr_progress}"
        filter_str = f"crop={crop_w}:{crop_h}:x='{x_expr}':y='{y_expr}'"
    return filter_str, crop_w, crop_h


def trim_clip(video_path, out_path, start, end, ratio_key=None, custom_ratio=None,
              pan_start=None, pan_end=None, src_dims=None, reencode_audio=True):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.0, end - start)
    if duration <= 0:
        raise FFmpegError(f"Invalid trim range: start={start} end={end}")
    filters = []
    if ratio_key:
        if src_dims is None:
            meta = probe(video_path)
            src_dims = (meta["width"], meta["height"])
        src_w, src_h = src_dims
        crop_filter, out_w, out_h = build_crop_pan_filter(
            src_w, src_h, ratio_key, custom_ratio, pan_start, pan_end, duration
        )
        filters.append(crop_filter)
    cmd = [FFMPEG_BIN, "-y", "-ss", str(start), "-to", str(end), "-i", str(video_path)]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
    ]
    if reencode_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", str(out_path)]
    _run(cmd, timeout=1800)
    return out_path


def split_video_at_points(video_path, split_points, out_dir, base_name=None):
    meta = probe(video_path)
    duration = meta["duration"]
    base_name = base_name or Path(video_path).stem
    points = sorted(set([0.0] + [float(p) for p in split_points if 0 < p < duration] + [duration]))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    segments = []
    for i in range(len(points) - 1):
        start, end = points[i], points[i + 1]
        seg_name = f"{base_name}_seg{i+1:02d}_{uuid.uuid4().hex[:6]}.mp4"
        seg_path = str(Path(out_dir) / seg_name)
        trim_clip(video_path, seg_path, start, end, src_dims=(meta["width"], meta["height"]))
        segments.append({"path": seg_path, "start": start, "end": end, "index": i + 1})
    return segments


def render_reel(video_path, out_path, start, end, ratio_key, custom_ratio=None,
                 pan_start=None, pan_end=None, volume=1.0, mute=False,
                 speed=1.0, brightness=None, contrast=None, saturation=None):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    meta = probe(video_path)
    src_w, src_h = meta["width"], meta["height"]
    vfilters = []
    crop_filter, out_w, out_h = build_crop_pan_filter(
        src_w, src_h, ratio_key, custom_ratio, pan_start, pan_end, max(0.0, end - start)
    )
    vfilters.append(crop_filter)
    if speed and speed != 1.0:
        vfilters.append(f"setpts={1/speed:.6f}*PTS")
    eq_parts = []
    if brightness is not None:
        eq_parts.append(f"brightness={brightness}")
    if contrast is not None:
        eq_parts.append(f"contrast={contrast}")
    if saturation is not None:
        eq_parts.append(f"saturation={saturation}")
    if eq_parts:
        vfilters.append("eq=" + ":".join(eq_parts))
    cmd = [FFMPEG_BIN, "-y", "-ss", str(start), "-to", str(end), "-i", str(video_path)]
    cmd += ["-vf", ",".join(vfilters)]
    if mute or not meta["has_audio"]:
        cmd += ["-an"]
    else:
        afilters = []
        if speed and speed != 1.0:
            remaining = speed
            stages = []
            while remaining > 2.0:
                stages.append(2.0)
                remaining /= 2.0
            while remaining < 0.5:
                stages.append(0.5)
                remaining /= 0.5
            stages.append(remaining)
            afilters.extend([f"atempo={s:.6f}" for s in stages])
        if volume != 1.0:
            afilters.append(f"volume={volume}")
        if afilters:
            cmd += ["-af", ",".join(afilters)]
        cmd += ["-c:a", "aac", "-b:a", "192k"]
    cmd += [
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_path),
    ]
    _run(cmd, timeout=1800)
    out_meta = probe(out_path)
    return {"path": out_path, "width": out_w, "height": out_h, "duration": out_meta["duration"]}


def list_video_files(folder):
    from app.config import Config
    exts = Config.ALLOWED_VIDEO_EXTENSIONS
    folder_path = Path(folder)
    if not folder_path.exists():
        return []
    return sorted(
        [str(p) for p in folder_path.iterdir() if p.is_file() and p.suffix.lower() in exts],
        key=lambda p: Path(p).name.lower(),
    )
