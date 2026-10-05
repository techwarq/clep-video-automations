"""Pinterest search + download — no login, no browser.

Uses the JSON resource endpoint pinterest.com's own web client calls
(BaseSearchResource); an anonymous session cookie from the homepage is enough.
Video pins come back as HLS playlists; the progressive 720p MP4 lives at the
same path with /hls/ -> /720p/. HLS via ffmpeg is the fallback.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path

import requests

from reels import config

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
BASE = "https://www.pinterest.com"
_session: requests.Session | None = None
_lock = threading.Lock()


def session() -> requests.Session:
    global _session
    with _lock:
        if _session is None:
            s = requests.Session()
            s.headers["User-Agent"] = UA
            try:
                s.get(BASE + "/", timeout=20)
            except requests.RequestException:
                pass
            _session = s
        return _session


def _find_video_list(obj, depth: int = 0) -> dict | None:
    """Video pins keep video_list under .videos; idea pins bury it in story_pin_data."""
    if depth > 8:
        return None
    if isinstance(obj, dict):
        vl = obj.get("video_list")
        if isinstance(vl, dict) and vl:
            return vl
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for v in children:
        found = _find_video_list(v, depth + 1)
        if found:
            return found
    return None


def _parse(pin: dict) -> dict | None:
    if not isinstance(pin, dict) or pin.get("type") not in (None, "pin"):
        return None
    title = (pin.get("grid_title") or pin.get("title") or pin.get("description") or "").strip()
    vl = _find_video_list(pin.get("videos")) or _find_video_list(pin.get("story_pin_data"))
    if vl:
        best = max(vl.values(), key=lambda v: (v.get("width") or 0) * (v.get("height") or 0))
        hls = best.get("url") or ""
        mp4 = hls.replace("/hls/", "/720p/").replace(".m3u8", ".mp4") if hls.endswith(".m3u8") else hls
        return {"id": str(pin.get("id")), "kind": "video", "title": title,
                "url": mp4, "hls": hls if hls.endswith(".m3u8") else None,
                "width": best.get("width") or 0, "height": best.get("height") or 0,
                "duration": (best.get("duration") or 0) / 1000.0, "thumb": best.get("thumbnail") or ""}
    images = pin.get("images") or {}
    orig = images.get("orig") or {}
    if orig.get("url"):
        return {"id": str(pin.get("id")), "kind": "image", "title": title, "url": orig["url"],
                "width": orig.get("width") or 0, "height": orig.get("height") or 0, "duration": 0.0,
                "thumb": (images.get("474x") or {}).get("url") or orig["url"]}
    return None


def search(query: str, scope: str = "pins", limit: int = 25) -> list[dict]:
    """scope='videos' returns video pins only; 'pins' mixes images and videos."""
    data = {"options": {"query": query, "scope": scope, "page_size": min(limit, 50)}, "context": {}}
    params = {"source_url": f"/search/{scope}/?q={urllib.parse.quote(query)}", "data": json.dumps(data)}
    headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest",
               "X-Pinterest-PWS-Handler": "www/search/[scope].js"}
    for attempt in range(3):
        try:
            r = session().get(f"{BASE}/resource/BaseSearchResource/get/", params=params,
                              headers=headers, timeout=30)
            r.raise_for_status()
            results = ((r.json().get("resource_response") or {}).get("data") or {}).get("results") or []
            return [p for p in (_parse(x) for x in results) if p][:limit]
        except (requests.RequestException, ValueError) as e:
            if attempt == 2:
                print(f"[pinterest] search {query!r} ({scope}) failed: {e}")
            time.sleep(1.5 * (attempt + 1))
    return []


def download(pin: dict, dest_dir: Path) -> Path | None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = ".mp4" if pin["kind"] == "video" else Path(urllib.parse.urlparse(pin["url"]).path).suffix or ".jpg"
    dest = dest_dir / f"{pin['kind']}_{pin['id']}{ext}"
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest
    try:
        with session().get(pin["url"], stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
    except requests.RequestException:
        dest.unlink(missing_ok=True)
        if not pin.get("hls"):
            return None
        subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-i", pin["hls"], "-c", "copy", str(dest)],
                       capture_output=True, timeout=180)
    if not dest.exists() or dest.stat().st_size < 10_000:
        dest.unlink(missing_ok=True)
        return None
    return dest
