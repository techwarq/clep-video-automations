"""Sound by default, for free: the film declares what happens (window.EVENTS), and this fills every visible action
the agent left silent with a library cue, puts the hit on the drop, the mute before it, and the logo sting.

    window.EVENTS = [[t, "kind"], …]   kinds: morph bloom collapse click type tick pop whoosh drop word impact success logo
                                              swipe arrive count
The agent's own cues always win; this only fills gaps. With no EVENTS at all, the film's big motion peaks get
quiet morph/tick cues so it is never silent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

from . import library

# kind → (warm id, cold id, gain dB). Warm = soft and organic, cold = dry and digital (04_sound.md).
PALETTE: Dict[str, tuple] = {
    "morph": ("warm_stretch", "cold_stretch", -9), "bloom": ("warm_open", "cold_burst", -7),
    "collapse": ("warm_collapse", "cold_collapse", -8), "click": ("warm_click", "dark_click", -7),
    "type": ("warm_typing", "cold_keys", -12), "tick": ("warm_tick", "dark_tick", -12),
    "pop": ("warm_pop_whatsapp", "cold_file", -11), "whoosh": ("warm_portal", "cold_zip", -7),
    "drop": ("warm_drop", "dark_absorb", -8), "word": ("warm_word", "dark_sub_word", -9),
    "impact": ("warm_iris", "cold_hit", -3), "success": ("warm_sent", "dark_verified_chime", -8),
    "logo": ("warm_logo", "cold_logo", -3), "swipe": ("warm_pullback", "cold_zip", -6),
    "arrive": ("warm_row", "cold_blip", -11), "count": ("cold_counter", "cold_counter", -12),
}
KINDS = sorted(PALETTE)


def palette(mx: dict) -> int:
    """0 = warm, 1 = cold. mix.json may say "palette": "warm"|"cold"; otherwise the music decides."""
    p = (mx.get("palette") or "").lower()
    if p in ("warm", "cold"):
        return 0 if p == "warm" else 1
    return 0 if str(mx.get("track", "")).startswith("warm") else 1


def read_events(index: Path) -> List[list]:
    from .check import Page
    pg = Page(index, scale=0.25)
    try:
        ev = pg.pg.evaluate("window.EVENTS || null")
    finally:
        pg.close()
    out = []
    for e in ev or []:
        t, k = (e.get("t"), e.get("kind")) if isinstance(e, dict) else (e[0], e[1])
        if k in PALETTE and t is not None:
            out.append([float(t), k])
    return sorted(out)


def motion_events(d: np.ndarray, fps: int = 30) -> List[list]:
    """No EVENTS declared: the film's own motion peaks (local maxima well above the typical change), ≥ 0.6 s apart."""
    if not len(d):
        return []
    med = float(np.median(d)) or 0.05; big = np.percentile(d, 97)
    out, last = [], -9.0
    for i in range(1, len(d) - 1):
        if d[i] >= d[i - 1] and d[i] >= d[i + 1] and d[i] > 3 * med + 0.5 and (i / fps) - last >= 0.6:
            out.append([round(i / fps, 3), "morph" if d[i] >= big else "tick"]); last = i / fps
    return out


def complete(mx: dict, events: List[list], grid: dict) -> tuple:
    """→ (cues, mutes, notes). Adds a cue for every event with no agent cue within 0.1 s, the impact on the drop,
    a ½-beat mute before it, and the logo sting. Repeats vary their pitch; never more than 3 sounds at one instant."""
    ids = {s["id"] for s in library.load()["sfx"]}
    w = palette(mx)
    cues = [dict(c) for c in mx.get("cues", []) if c.get("id") in ids]
    mutes = [list(m) for m in mx.get("mute", [])]
    added: Dict[str, int] = {}

    own = [float(c["t"]) for c in cues]                              # the agent's cues: it already covered these moments

    def near(t, dt):
        return sum(1 for c in cues if abs(float(c["t"]) - t) < dt)

    def add(t, kind, n):
        sid, gain = PALETTE[kind][w], PALETTE[kind][2]
        if sid not in ids or any(abs(x - t) < 0.1 for x in own) or near(t, 0.06) >= 3 \
                or any(c["id"] == sid and abs(float(c["t"]) - t) < 0.06 for c in cues):
            return
        rate = round(0.94 + 0.14 * ((n * 0.618) % 1.0), 3)          # deterministic variety, 0.94–1.08
        cues.append({"t": round(t, 3), "id": sid, "gain": gain, **({"rate": rate} if n else {})})
        added[kind] = added.get(kind, 0) + 1

    seen: Dict[str, int] = {}
    for t, k in events:
        add(t, k, seen.get(k, 0)); seen[k] = seen.get(k, 0) + 1
    dur = float(mx.get("duration") or grid["dur"])
    drop = grid.get("drop_t")
    if drop and 0 < drop < dur:
        if not any(abs(float(c["t"]) - drop) < 0.15 and PALETTE["impact"][w] == c["id"] for c in cues) and not near(drop, 0.15):
            add(drop - 0.04, "impact", 0)
        if not any(a <= drop - 0.05 <= a + b for a, b in mutes):
            mutes.append([round(drop - grid["beat"] / 2, 3), round(grid["beat"] / 2, 3)])
            added["mute before drop"] = 1
    if not any(c["id"] == PALETTE["logo"][w] for c in cues) and not any(k == "logo" for _, k in events):
        add(max(0.0, dur - 3.2), "logo", 0)
    cues.sort(key=lambda c: c["t"])
    notes = ", ".join(f"{k} ×{n}" for k, n in added.items())
    return cues, mutes, notes


def problems(mx: dict, events: List[list], grid: dict) -> List[str]:
    """Free notes for the agent about its sound (the auto pass will fill gaps anyway, but its own cues are better)."""
    out = []
    dur = float(mx.get("duration") or grid["dur"])
    n = len(mx.get("cues", []))
    if not events:
        out.append("no window.EVENTS: declare every visible action as [t, kind] so each one gets a sound "
                   f"(kinds: {', '.join(KINDS)})")
    if n < dur * 0.6:
        out.append(f"thin sound: {n} cues for {dur:.0f}s (the references use 1–2 per second); "
                   f"missing ones will be filled from EVENTS")
    drop = grid.get("drop_t")
    if drop and not any(abs(float(c.get("t", -9)) - drop) < 0.15 for c in mx.get("cues", [])):
        out.append(f"no hit on the drop at {drop:.2f}s")
    return out
