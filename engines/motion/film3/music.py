"""Film music from a library track: join whole source bars (sections) → the film's own bar grid.

Film t = 0 is the first bar of the first section, so film bar n starts at (n-1)·bar exactly.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List

import numpy as np

from . import library
from .timing import analyze

SR = 48000
FACTS = library.LIB / "facts"


def track(tid: str) -> dict:
    m = next((m for m in library.load()["music"] if m["id"] == tid), None)
    if not m:
        raise ValueError(f"unknown music track {tid}")
    f = FACTS / f"{tid}.json"
    if not f.exists():
        FACTS.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(analyze(library.LIB / "music" / f"{tid}.mp3", m["bpm"])))
    return {**m, "facts": json.loads(f.read_text()), "file": library.LIB / "music" / f"{tid}.mp3"}


def catalog_text() -> str:
    out = []
    for m in library.load()["music"]:
        f = track(m["id"])["facts"]
        out.append(f"- {m['id']}: {m['desc']}. {f['bpm']} bpm, bar {f['bar']:.3f}s, {len(f['bars'])} bars, DROP = bar {f['drop']['bar']}, "
                   f"outro bar {f['outro_bar']}. energy per bar: " + " ".join(f"{b['bar']}:{b['energy']:.1f}" for b in f["bars"]))
    return "MUSIC LIBRARY (bars are whole bars of the track)\n" + "\n".join(out)


def sfx_text() -> str:
    return "SFX LIBRARY (id: description)\n" + "\n".join(f"- {s['id']}: {s['desc'][:100]}" for s in library.load()["sfx"])


def plan(tid: str, sections: List[List[int]]) -> dict:
    """Film grid for the chosen sections (no audio written)."""
    tr = track(tid); f = tr["facts"]; nb = len(f["bars"])
    secs = [[max(1, int(a)), min(nb, int(b))] for a, b in (sections or [[1, nb]]) if int(b) >= int(a)]
    if not secs:
        secs = [[1, nb]]
    bars, j = [], 0
    for a, b in secs:
        for sb in range(a, b + 1):
            j += 1
            src = f["bars"][sb - 1]
            bars.append({"bar": j, "t": round((j - 1) * f["bar"], 3), "src": sb, "energy": src["energy"],
                         "drop": sb == f["drop"]["bar"], "outro": sb == f["outro_bar"], "join": sb == a and j > 1})
    drop = next((b for b in bars if b["drop"]), None)
    return {"track": tid, "sections": secs, "bpm": f["bpm"], "beat": f["beat"], "bar": f["bar"], "bars": bars,
            "drop_bar": drop["bar"] if drop else None, "drop_t": drop["t"] if drop else None,
            "dur": round(len(bars) * f["bar"], 3), "src_first": f["first_downbeat"]}


def table(g: dict) -> str:
    rows = [f"bar {b['bar']:2d} @ {b['t']:6.2f}s  energy {b['energy']:.1f}" + ("   <- DROP (biggest moment goes here)" if b["drop"] else "")
            + ("   (outro: calm, the name)" if b["outro"] else "") + ("   (section join)" if b["join"] else "") for b in g["bars"]]
    return (f"FILM MUSIC: {g['track']} · {g['bpm']} bpm · beat {g['beat']:.4f}s · bar {g['bar']:.4f}s · {len(g['bars'])} bars · "
            f"{g['dur']}s\nTimes are written \"bar:beat\" (beat 1–4, may be 1.5 for the & of 1, 1.25 for a 16th).\n" + "\n".join(rows))


def _decode(p: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)


def render(g: dict, out: Path) -> Path:
    """Write the film's music (sections joined on bar lines with 6 ms crossfades)."""
    tr = track(g["track"]); x = _decode(tr["file"]); bar = g["bar"]; first = g["src_first"]
    xf = int(0.006 * SR); parts = []
    for a, b in g["sections"]:
        s0, s1 = int((first + (a - 1) * bar) * SR), int((first + b * bar) * SR)
        seg = x[s0:min(len(x), s1 + xf)].copy()
        if len(seg) < s1 - s0:
            seg = np.vstack([seg, np.zeros((s1 - s0 - len(seg), 2), np.float32)])
        parts.append(seg)
    y = parts[0][: len(parts[0]) - xf] if len(parts) > 1 else parts[0]
    for i, p in enumerate(parts[1:], 1):
        ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
        tail = parts[i - 1][len(parts[i - 1]) - xf:]
        head = p[:xf] * ramp + tail * (1 - ramp)
        body = p[xf: len(p) - xf] if i < len(parts) - 1 else p[xf:]
        y = np.vstack([y, head, body])
    n = int(g["dur"] * SR); y = y[:n]
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", str(out)],
                   input=y.astype(np.float32).tobytes(), check=True)
    return out
