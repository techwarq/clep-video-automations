"""Reusable, already-paid sound: a catalog of SFX and music tracks the director picks from (no generation).

    python3 -m film3.library add-music <file.mp3> <id> "<description>" [--bpm 120]
    python3 -m film3.library add-sfx <file.mp3> <id> "<description>"
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LIB = HERE / "library"
CAT = LIB / "catalog.json"


def _dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout
    return round(float(out.strip() or 0), 2)


def load() -> dict:
    return json.loads(CAT.read_text()) if CAT.exists() else {"sfx": [], "music": []}


def save(cat: dict):
    LIB.mkdir(parents=True, exist_ok=True)
    CAT.write_text(json.dumps(cat, indent=1))


def estimate_bpm(p: Path) -> float:
    from .timing import _load, SR
    x = _load(p); hop, win = 256, 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, win)[::hop] * np.hanning(win)
    S = np.abs(np.fft.rfft(fr, axis=1)); flux = np.maximum(0, np.diff(np.log1p(S * 10), axis=0)).sum(1); flux -= flux.mean()
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]; lags = np.arange(len(ac)) * hop / SR
    m = (lags > 60 / 140) & (lags < 60 / 80)
    return round(60 / lags[m][np.argmax(ac[m])], 1)


def add_sfx(cat: dict, src: Path, sid: str, desc: str):
    if not src.exists() or any(s["id"] == sid for s in cat["sfx"]):
        return
    dest = LIB / "sfx" / f"{sid}.mp3"; dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    cat["sfx"].append({"id": sid, "desc": desc, "seconds": _dur(dest)})


def add_music(cat: dict, src: Path, mid: str, desc: str, bpm: float = None):
    from .timing import analyze
    if not src.exists() or any(m["id"] == mid for m in cat["music"]):
        return
    dest = LIB / "music" / f"{mid}.mp3"; dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    bpm = bpm or estimate_bpm(dest)
    f = analyze(dest, bpm)
    cat["music"].append({"id": mid, "desc": desc, "bpm": f["bpm"], "duration": f["duration"], "first_downbeat": f["first_downbeat"],
                         "drop_t": f["drop"]["t"], "drop_bar": f["drop"]["bar"], "outro_bar": f["outro_bar"],
                         "shape": " ".join(f"{b['energy']:.1f}" for b in f["bars"])})


def prompt_catalog(cat: dict) -> str:
    sf = "\n".join(f"- {s['id']} ({s['seconds']}s): {s['desc'][:110]}" for s in cat["sfx"])
    mu = "\n".join(f"- {m['id']}: {m['bpm']} bpm, {m['duration']}s, drop at {m['drop_t']}s (bar {m['drop_bar']}), outro bar {m['outro_bar']}. {m['desc']}. energy per bar: {m['shape']}"
                   for m in cat["music"])
    return f"MUSIC LIBRARY\n{mu}\n\nSFX LIBRARY\n{sf}"


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "add-music":
        c = load(); bpm = float(a[a.index("--bpm") + 1]) if "--bpm" in a else None
        add_music(c, Path(a[1]), a[2], a[3], bpm); save(c)
    elif a and a[0] == "add-sfx":
        c = load(); add_sfx(c, Path(a[1]), a[2], a[3]); save(c)
