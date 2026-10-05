#!/usr/bin/env python3
"""Render a v2 film page (window.boot(), window.seek(t) -> Promise) to frames.

  capture.py <film.html> stills <out_dir> <t,t,...>          [--sub 3]
  capture.py <film.html> frames <out_dir> <t0> <t1> [--fps 60 --sub 3 --workers 6]

Each output frame averages `sub` sub-frames spread over a 180-degree shutter (real motion blur).
"""
import argparse
import io
import math
from multiprocessing import Process
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

SHUTTER = 0.5  # fraction of a frame interval the virtual shutter is open


def open_page(p, html):
    b = p.chromium.launch(args=["--disable-web-security", "--allow-file-access-from-files", "--disable-gpu-vsync"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.on("pageerror", lambda e: print("[pageerror]", e, flush=True))
    pg.on("console", lambda m: m.type == "error" and print("[console]", m.text, flush=True))
    pg.add_init_script("{const a=CanvasRenderingContext2D.prototype.arc;CanvasRenderingContext2D.prototype.arc=function(x,y,r,s,e,c){return a.call(this,x,y,Math.max(0,r),s,e,c)}}")
    pg.goto(Path(html).resolve().as_uri())
    pg.evaluate("window.boot()")
    return b, pg


def shot(pg, t, sub, fps):
    if sub <= 1:
        pg.evaluate(f"window.seek({t:.6f})")
        return np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png"))).convert("RGB"), dtype=np.float32)
    acc = None
    for k in range(sub):
        tk = t + ((k + 0.5) / sub - 0.5) * SHUTTER / fps
        pg.evaluate(f"window.seek({max(0.0, tk):.6f})")
        a = np.asarray(Image.open(io.BytesIO(pg.screenshot(type="png"))).convert("RGB"), dtype=np.float32)
        acc = a if acc is None else acc + a
    return acc / sub


def save(arr, dest):
    Image.fromarray(np.clip(arr + 0.5, 0, 255).astype(np.uint8)).save(dest, quality=95, subsampling=0)


def worker(html, out, frames, fps, sub, wid):
    with sync_playwright() as p:
        b, pg = open_page(p, html)
        frames = [f for f in frames if not (Path(out) / f"{f:05d}.jpg").exists()]
        for n, fidx in enumerate(frames):
            save(shot(pg, fidx / fps, sub, fps), Path(out) / f"{fidx:05d}.jpg")
            if n % 60 == 0:
                print(f"[w{wid}] {n}/{len(frames)}", flush=True)
        b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html"); ap.add_argument("mode"); ap.add_argument("out"); ap.add_argument("args", nargs="*")
    ap.add_argument("--fps", type=int, default=60); ap.add_argument("--sub", type=int, default=3)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.mode == "stills":
        ts = [float(x) for x in a.args[0].split(",")]
        with sync_playwright() as p:
            b, pg = open_page(p, a.html)
            for t in ts:
                save(shot(pg, t, a.sub, a.fps), out / f"t{t:06.2f}.jpg")
                print(f"[still] {t}")
            b.close()
        return
    t0, t1 = float(a.args[0]), float(a.args[1])
    idx = list(range(int(round(t0 * a.fps)), int(round(t1 * a.fps))))
    chunk = math.ceil(len(idx) / a.workers)
    procs = [Process(target=worker, args=(a.html, str(out), idx[i * chunk:(i + 1) * chunk], a.fps, a.sub, i))
             for i in range(a.workers) if idx[i * chunk:(i + 1) * chunk]]
    for pr in procs: pr.start()
    for pr in procs: pr.join()
    bad = [pr.exitcode for pr in procs if pr.exitcode]
    if bad:
        raise SystemExit(f"workers failed: {bad}")
    print(f"[frames] {len(idx)} frames -> {out}")


if __name__ == "__main__":
    main()
