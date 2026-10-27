"""
Screencast: lossless-looking capture of a Playwright page via the Chrome
DevTools screencast, instead of Playwright's record_video (VP8 at ~0.4 Mbps,
25 fps, 1x pixels — soft text that falls apart once polish zooms in).

  - 2x device pixels (the browser must be launched with
    --force-device-scale-factor=SCALE, or frames come back at 1x),
  - a frame on every repaint (~60-90 fps while something moves, none while
    the page is still — polish holds the last frame),
  - every frame stamped with the browser's own paint time, mapped onto the
    agent's clock, so cursor, clicks and state changes line up exactly.

Frames are JPEG files in <out_dir>/frames; frames.json lists [{t, f}].
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

SCALE = 2          # device pixels per CSS pixel in the capture
JPEG_QUALITY = 92  # visually lossless for UI; ~100-150 KB per 2880x1800 frame

def scale_for(quality: str | None) -> int:
    return 3 if quality == "4k" else SCALE


def launch_args(scale: int = SCALE) -> list[str]:
    return [f"--force-device-scale-factor={scale}"]


class Screencast:
    def __init__(self, ctx, page, out_dir: Path, clock, viewport: dict, scale: int = SCALE):
        self.scale = scale
        self.dir = Path(out_dir) / "frames"
        self.dir.mkdir(parents=True, exist_ok=True)
        for old in self.dir.glob("*.jpg"):
            old.unlink()
        self.clock = clock
        self.viewport = viewport
        self.frames: list[list] = []   # [browser_ts | None, received_at, file]
        self.offset: float | None = None
        self.cdp = ctx.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", self._on_frame)

    def _on_frame(self, f: dict) -> None:
        recv = self.clock()
        ts = (f.get("metadata") or {}).get("timestamp")
        if ts is not None:
            # The smallest (received - painted) gap is the transport latency
            # floor; using it maps paint times onto our clock without jitter.
            off = recv - ts
            self.offset = off if self.offset is None else min(self.offset, off)
        name = f"{len(self.frames):06d}.jpg"
        (self.dir / name).write_bytes(base64.b64decode(f["data"]))
        self.frames.append([ts, recv, name])
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": f["sessionId"]})
        except Exception:
            pass

    def start(self) -> None:
        self.cdp.send("Page.startScreencast", {
            "format": "jpeg", "quality": JPEG_QUALITY,
            "maxWidth": self.viewport["width"] * self.scale,
            "maxHeight": self.viewport["height"] * self.scale,
            "everyNthFrame": 1,
        })

    def stop(self) -> dict:
        try:
            self.cdp.send("Page.stopScreencast")
        except Exception:
            pass
        out, last = [], -1.0
        for ts, recv, name in self.frames:
            t = ts + self.offset if (ts is not None and self.offset is not None) else recv
            if t <= last:            # keep times strictly increasing
                t = last + 1e-4
            out.append({"t": round(t, 4), "f": name})
            last = t
        index = {"dir": str(self.dir), "scale": self.scale, "frames": out}
        (self.dir.parent / "frames.json").write_text(json.dumps(index))
        return index
