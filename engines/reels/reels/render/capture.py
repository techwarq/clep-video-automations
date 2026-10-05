"""comp.html -> MP4. Frames are captured in parallel chunks, each piped straight
into its own ffmpeg encoder, then concatenated and muxed with the audio mix."""

from __future__ import annotations

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from reels import config
from reels.render import audio
from reels.render.browser import open_page


def _encode_cmd(out: Path) -> list[str]:
    return [config.FFMPEG, "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(config.FPS),
            "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "17",
            "-pix_fmt", "yuv420p", "-r", str(config.FPS), str(out)]


def _chunk(html: str, f0: int, f1: int, out: str) -> tuple[str, float]:
    t0 = time.time()
    with open_page(Path(html)) as page:
        enc = subprocess.Popen(_encode_cmd(Path(out)), stdin=subprocess.PIPE)
        for i in range(f0, f1):
            page.seek(i / config.FPS)
            enc.stdin.write(page.jpeg())
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError(f"encoder failed for frames {f0}-{f1}")
        errs = page.errors()
        if errs:
            print(f"[render] frames {f0}-{f1} page errors: {errs[:3]}")
    return out, time.time() - t0


def video(project, workers: int = 4) -> Path:
    """Silent video of comp.html for the reel's full duration."""
    reel = project.write_data()
    n = int(round(reel["dur"] * config.FPS))
    workers = max(1, min(workers, n // 30 or 1))
    tmp = project.root / ".render"
    tmp.mkdir(exist_ok=True)
    bounds = [round(n * k / workers) for k in range(workers + 1)]
    jobs = [(str(project.html), bounds[k], bounds[k + 1], str(tmp / f"part{k:02d}.mp4")) for k in range(workers)]
    t0 = time.time()
    print(f"[render] {n} frames ({reel['dur']:.1f}s) on {workers} workers...")
    with ThreadPoolExecutor(workers) as ex:   # one Playwright + Chromium per thread
        parts = [r[0] for r in ex.map(_chunk, *zip(*jobs))]
    listing = tmp / "parts.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    silent = tmp / "video.mp4"
    subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-c", "copy", str(silent)], check=True)
    print(f"[render] frames done in {time.time() - t0:.0f}s ({n / max(1e-3, time.time() - t0):.1f} fps)")
    return silent


def render(project, out: Path | None = None, workers: int = 4) -> Path:
    """Full render: frames + audio mix -> output/<project>.mp4 (and a cover jpg)."""
    silent = video(project, workers)
    with open_page(project.html) as page:
        cues = page.cues()
    dur = project.write_data()["dur"]
    mix = audio.mix(project, cues, dur)
    out = Path(out) if out else config.OUTPUT_DIR / f"{project.root.name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-i", str(silent), "-i", str(mix),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)], check=True)
    subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-ss", f"{min(1.0, dur / 3):.2f}", "-i", str(out),
                    "-frames:v", "1", "-q:v", "3", str(out.with_suffix(".jpg"))])
    print(f"[render] -> {out}")
    return out
