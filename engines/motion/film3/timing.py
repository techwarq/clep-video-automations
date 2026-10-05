"""Measure the real track: beat grid, per-bar energy, the drop (re-phased onto a downbeat), risers, quiet, outro."""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 22050


def _load(path: Path) -> np.ndarray:
    wav = path.with_suffix(".an.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
    w = wave.open(str(wav))
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def analyze(music: Path, bpm: float) -> dict:
    x = _load(music)
    dur = len(x) / SR
    hop, win = 128, 1024
    fr = np.lib.stride_tricks.sliding_window_view(x, win)[::hop] * np.hanning(win)
    S = np.abs(np.fft.rfft(fr, axis=1))
    f = np.fft.rfftfreq(win, 1 / SR)
    t = (np.arange(len(S)) + 0.5) * hop / SR + win / 2 / SR
    flux = np.maximum(0, np.diff(np.log1p(S * 10), axis=0, prepend=np.log1p(S[:1] * 10))).sum(1)
    lowflux = np.maximum(0, np.diff(np.log1p(S[:, f < 150] * 10), axis=0, prepend=np.log1p(S[:1, f < 150] * 10))).sum(1)

    # period + phase: maximise onset energy on the grid
    best = None
    for p in np.linspace(60 / bpm * 0.985, 60 / bpm * 1.015, 41):
        for ph in np.arange(0, p, 0.004):
            idx = np.searchsorted(t, np.arange(ph, t[-1], p))
            idx = idx[idx < len(flux)]
            sc = flux[idx].mean() + 0.5 * lowflux[idx].mean()
            if best is None or sc > best[0]:
                best = (sc, p, ph)
    _, beat, phase = best
    beats = np.arange(phase, dur, beat)

    def band_energy(a, b, lo, hi):
        m = (t >= a) & (t < b)
        if not m.any():
            return 0.0
        return float(np.log1p(S[m][:, (f >= lo) & (f < hi)].sum(1)).mean())

    low = np.array([band_energy(b0, b0 + beat, 20, 150) for b0 in beats])
    hi = np.array([band_energy(b0, b0 + beat, 3000, 11000) for b0 in beats])
    mid = np.array([band_energy(b0, b0 + beat, 600, 3000) for b0 in beats])
    tot = np.array([float(np.sqrt(np.mean(x[int(b0 * SR):int((b0 + beat) * SR)] ** 2) + 1e-12)) for b0 in beats])

    # drop = biggest onset jump across low/mid/high bands (half-beat windows, 16th resolution), snapped to the grid
    def band(a, b, lo, hi_):
        m = (t >= a) & (t < b)
        return float(np.log1p(S[m][:, (f >= lo) & (f < hi_)].sum(1)).mean()) if m.any() else 0.0
    hb, best = beat / 2, None
    for c in np.arange(dur * 0.15, dur * 0.85, beat / 4):
        sc = 0.0
        for lo, hi_ in ((20, 150), (150, 3000), (3000, 11000)):
            sc += np.mean([band(c + i * hb, c + (i + 1) * hb, lo, hi_) for i in range(2)]) - \
                  np.mean([band(c - (i + 1) * hb, c - i * hb, lo, hi_) for i in range(2)])
        if best is None or sc > best[0]:
            best = (sc, c)
    di = int(np.argmin(np.abs(beats - best[1] - 0.03)))
    down = di % 4                                   # the drop defines the downbeat phase
    first = float(beats[down])
    bar = 4 * beat
    nb = int((dur - first) // bar)
    en = tot / (tot.max() + 1e-9)
    bars = []
    for j in range(nb):
        i0 = down + 4 * j
        sl = slice(i0, i0 + 4)
        bars.append({"bar": j + 1, "t": round(first + j * bar, 3), "energy": round(float(en[sl].mean()), 2),
                     "low": round(float(low[sl].mean() / (low.max() + 1e-9)), 2), "bright": round(float(hi[sl].mean() / (hi.max() + 1e-9)), 2)})
    # risers: mid+high energy climbing steadily for ≥ 2 bars
    risers = []
    for j in range(2, len(bars)):
        a, b_ = down + 4 * (j - 2), down + 4 * j
        seg = (mid[a:b_] - mid.min()) / (np.ptp(mid) + 1e-9)
        if len(seg) > 6 and np.polyfit(np.arange(len(seg)), seg, 1)[0] > 0.03 and seg[-2:].mean() > 0.6:
            risers.append(bars[j]["bar"])
    quiet = [b_["bar"] for b_ in bars if b_["energy"] < 0.25]
    loud = [b_["bar"] for b_ in bars if b_["energy"] > 0.7]
    # outro: first bar after the last loud bar where energy falls below 35%
    outro = next((b_["bar"] for b_ in bars if loud and b_["bar"] > max(loud) and b_["energy"] < 0.35), None)
    drop_bar = int(round((beats[di] - first) / bar)) + 1
    film_end = min(dur, first + (nb + 0.25) * bar)
    facts = {"bpm": round(60 / beat, 2), "beat": round(float(beat), 5), "bar": round(float(bar), 5), "first_downbeat": round(first, 4),
             "pre_roll": round(first, 3), "duration": round(float(dur), 3), "film_end": round(float(film_end), 3),
             "drop": {"bar": int(drop_bar), "t": round(float(first + (drop_bar - 1) * bar), 3)}, "risers_into_bar": [int(r) for r in risers],
             "quiet_bars": [int(q) for q in quiet], "loud_bars": [int(l) for l in loud], "outro_bar": int(outro) if outro else None, "bars": bars}
    return facts


def table(facts: dict) -> str:
    rows = [f"bar {b['bar']:2d} @ {b['t']:6.2f}s  energy {b['energy']:.2f}  low {b['low']:.2f}  bright {b['bright']:.2f}"
            + ("   <- DROP" if b["bar"] == facts["drop"]["bar"] else "")
            + ("   (riser into this bar)" if b["bar"] in facts["risers_into_bar"] else "")
            + ("   (outro starts)" if b["bar"] == facts["outro_bar"] else "") for b in facts["bars"]]
    return (f"BPM {facts['bpm']} · beat {facts['beat']}s · bar {facts['bar']}s · first downbeat {facts['first_downbeat']}s "
            f"(t=0..{facts['first_downbeat']}s is pre-roll) · track {facts['duration']}s · film ends at {facts['film_end']}s\n" + "\n".join(rows))


if __name__ == "__main__":
    import sys
    fct = analyze(Path(sys.argv[1]), float(sys.argv[2]))
    print(table(fct))
    print(json.dumps({k: v for k, v in fct.items() if k != "bars"}, indent=1))
