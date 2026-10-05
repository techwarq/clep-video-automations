"""Turn downloaded/user files into what the HTML runtime reads.

Headless Chromium can't decode H.264 and seeking <video> per frame is slow and
inexact, so footage becomes a numbered JPEG sequence (media/<key>/00001.jpg)
at the reel's fps. Stills are normalised to JPEG. Originals stay in raw/ for audio.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from reels import config

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MAX_SECONDS = 25.0          # footage longer than this is trimmed (talking heads pass their full length)


def probe(path: Path) -> dict | None:
    """{width, height, duration, audio} of a media file, or None if unreadable."""
    try:
        out = subprocess.run(
            [config.FFPROBE, "-v", "error", "-show_entries",
             "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30).stdout
        j = json.loads(out)
        streams = j.get("streams") or []
        v = next((s for s in streams if s.get("codec_type") == "video"), {})
        return {"width": v.get("width") or 0, "height": v.get("height") or 0,
                "duration": float((j.get("format") or {}).get("duration") or 0),
                "audio": any(s.get("codec_type") == "audio" for s in streams)}
    except Exception:
        return None


def duration(path: Path) -> float:
    return (probe(path) or {}).get("duration", 0.0)


def _scale_filter() -> str:
    # Short side to 1080 (never upscale) so a full-bleed cover crop stays sharp.
    return ("scale='if(gt(iw,ih),-2,min(1080,iw))':'if(gt(iw,ih),min(1080,ih),-2)':flags=lanczos")


def prepare(project_root: Path, key: str, src: Path, start: float = 0.0,
            max_seconds: float | None = MAX_SECONDS, note: str = "") -> dict:
    """Extract one asset into media/. Returns its media.json entry."""
    src = Path(src)
    info = probe(src) or {}
    media = project_root / "media"
    raw = project_root / "raw" / f"{key}{src.suffix.lower()}"
    if src.resolve() != raw.resolve():
        shutil.copy(src, raw)
    if src.suffix.lower() in VIDEO_EXT:
        out = media / key
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        dur = max(0.0, info.get("duration", 0.0) - start)
        if max_seconds:
            dur = min(dur, max_seconds)
        subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
                        "-i", str(raw), "-vf", f"fps={config.FPS},{_scale_filter()}", "-q:v", "3",
                        str(out / "%05d.jpg")], check=True)
        frames = len(list(out.glob("*.jpg")))
        if not frames:
            raise RuntimeError(f"[media] no frames extracted from {src}")
        return {"kind": "video", "dir": f"media/{key}", "frames": frames, "fps": config.FPS,
                "dur": round(frames / config.FPS, 3), "w": info.get("width", 0), "h": info.get("height", 0),
                "start": start, "audio": info.get("audio", False), "path": str(raw), "note": note}
    dst = media / f"{key}.jpg"
    subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-i", str(raw), "-vf", _scale_filter(),
                    "-q:v", "2", "-frames:v", "1", str(dst)], check=True)
    from PIL import Image
    with Image.open(dst) as im:
        w, h = im.size
    return {"kind": "image", "src": f"media/{key}.jpg", "w": w, "h": h, "dur": 0,
            "path": str(raw), "note": note}


def add(project, key: str, src: Path, **kw) -> dict:
    """prepare() + record in the project's media.json."""
    entry = prepare(project.root, key, src, **kw)
    m = project.media
    m[key] = entry
    project.write("media.json", m)
    kind = f"{entry['dur']:.1f}s video" if entry["kind"] == "video" else "image"
    print(f"[media] {key}: {kind} {entry['w']}x{entry['h']}")
    return entry
