"""Final render: frames (60 fps, motion blur, parallel) → events → mix → H.264."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .mix import mix

HERE = Path(__file__).resolve().parent


def events(index: Path) -> list:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files", "--disable-web-security"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080}); pg.set_default_timeout(180000)
        pg.goto(index.as_uri()); pg.evaluate("window.boot()")
        ev = pg.evaluate("window.F2EVENTS")
        b.close()
    return ev


def frames(index: Path, out: Path, duration: float, fps: int = 60, sub: int = 3, workers: int = 6):
    out.mkdir(parents=True, exist_ok=True)
    n = int(round(duration * fps))
    for attempt in range(3):                          # capture.py skips frames that already exist → resumable
        subprocess.run([sys.executable, str(HERE / "capture.py"), str(index), "frames", str(out), "0", f"{duration:.4f}",
                        "--fps", str(fps), "--sub", str(sub), "--workers", str(workers)])
        have = len(list(out.glob("*.jpg")))
        if have >= n:
            return n
        print(f"[render] {have}/{n} frames, retrying missing ones")
    raise RuntimeError(f"render incomplete: {len(list(out.glob('*.jpg')))}/{n} frames")


def encode(frames_dir: Path, wav: Path, dest: Path, fps: int = 60, crf: int = 16):
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-start_number", "0", "-i", str(frames_dir / "%05d.jpg"),
                    "-i", str(wav), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-tune", "grain",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "256k", "-shortest", str(dest)], check=True)
    return dest


def final(work: Path, index: Path, duration: float, music: Path, sfx_dir: Path, dest: Path, workers: int = 6) -> Path:
    ev = events(index)
    (work / "events.json").write_text(json.dumps(ev, indent=1))
    fr = work / "frames"
    frames(index, fr, duration, workers=workers)
    wav = mix(ev, music, duration, sfx_dir, work / "mix.wav")
    return encode(fr, wav, dest)
