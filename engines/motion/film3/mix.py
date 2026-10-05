"""Sound mix from the runtime's exported events: Foley cues on exact times + music automation, mastered to -14 LUFS.

events: [{id, t, gain, dur?, rate?, pan?}] where id is an SFX palette id, or a music automation:
  @mute {t, dur}          hard mute of the music (silence before a hit)
  @duck {t, gain, dur}    dip the music by `gain` dB
  @lowpass {t, dur, hz0, hz1}  sweep a low-pass over the music (underwater / muffled)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import List

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

SR = 48000


def decode(path: Path, rate: float = 1.0) -> np.ndarray:
    af = f"asetrate={int(SR * rate)},aresample={SR}" if abs(rate - 1.0) > 1e-3 else "anull"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-af", af, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def _lowpass(x: np.ndarray, hz: np.ndarray, block=256) -> np.ndarray:
    out = np.empty_like(x); zi = None
    for s in range(0, len(x), block):
        f = float(np.clip(hz[min(s, len(hz) - 1)], 60, 19000))
        sos = butter(2, f, 'low', fs=SR, output='sos')
        if zi is None:
            zi = np.stack([sosfilt_zi(sos) * x[0, c] for c in range(2)], axis=-1)
        seg = x[s:s + block]; y = np.empty_like(seg)
        for c in range(2):
            y[:, c], zi[..., c] = sosfilt(sos, seg[:, c], zi=zi[..., c])
        out[s:s + block] = y
    return out


def mix(events: List[dict], music: Path, duration: float, sfx_dir: Path, out_wav: Path, music_db: float = -2.5) -> Path:
    n = int(duration * SR)
    mus = decode(music)[:n]
    if len(mus) < n:
        mus = np.vstack([mus, np.zeros((n - len(mus), 2), np.float32)])
    tt = np.arange(n) / SR
    gain = np.full(n, music_db, np.float32)
    lp = np.full(n, 20000.0, np.float32)
    for e in events:
        a = int(max(0, e["t"]) * SR)
        if e["id"] == "@mute":
            b = min(n, int((e["t"] + e.get("dur", 0.5)) * SR))
            ramp = int(0.012 * SR)
            gain[a:b] = -80
            if a - ramp > 0:
                gain[a - ramp:a] = np.minimum(gain[a - ramp:a], np.linspace(music_db, -80, ramp))
        elif e["id"] == "@duck":
            b = min(n, int((e["t"] + e.get("dur", 0.6)) * SR))
            if b > a:
                gain[a:b] += np.interp(np.arange(b - a), [0, 0.12 * (b - a), b - a], [0, e.get("gain", -6), 0]).astype(np.float32)
        elif e["id"] == "@lowpass":
            b = min(n, int((e["t"] + e.get("dur", 2.0)) * SR))
            if b > a:
                lp[a:b] = np.geomspace(e.get("hz0", 350), e.get("hz1", 1500), b - a)
    # music tail fade
    fade = int(min(1.5, duration * 0.05) * SR); gain[-fade:] = np.minimum(gain[-fade:], np.linspace(music_db, -40, fade))
    if (lp < 19999).any():
        mus = _lowpass(mus, lp)
    bus = mus * (10 ** (gain / 20))[:, None]
    for e in events:
        if e["id"].startswith("@"):
            continue
        f = sfx_dir / f"{e['id']}.mp3"
        if not f.exists():
            print(f"[mix] missing sfx {e['id']}")
            continue
        clip = decode(f, e.get("rate", 1.0))
        if e.get("dur"):
            clip = clip[:int(max(0.05, e["dur"]) * SR)]
        k = min(len(clip), int(0.04 * SR)); clip[-k:] *= np.linspace(1, 0, k, dtype=np.float32)[:, None]
        k = min(len(clip), 64); clip[:k] *= np.linspace(0, 1, k, dtype=np.float32)[:, None]
        pan = float(e.get("pan", 0)); clip = clip * np.array([min(1, 1 - pan), min(1, 1 + pan)], np.float32)
        a = int(max(0, e["t"]) * SR)
        if a >= n:
            continue
        seg = clip[:n - a]
        bus[a:a + len(seg)] += seg * 10 ** (float(e.get("gain", 0)) / 20)
    k = int(0.06 * SR); bus[-k:] *= np.linspace(1, 0, k, dtype=np.float32)[:, None]
    raw = out_wav.with_suffix(".raw.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-", str(raw)],
                   input=bus.astype(np.float32).tobytes(), check=True)
    meas = subprocess.run(["ffmpeg", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    j = json.loads(meas[meas.rfind("{"):meas.rfind("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
          f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", ln, "-ar", str(SR), str(out_wav)], check=True)
    raw.unlink()
    print(f"[mix] {out_wav} · {sum(1 for e in events if not e['id'].startswith('@'))} cues")
    return out_wav
