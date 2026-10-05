"""Spoken words with per-word timings -> project voice.wav + words.json.

Three sources:
  tts()          ElevenLabs /with-timestamps (PAID — callers must get a yes first; see estimate())
  from_audio()   your own recording or a talking-head video, timed locally with faster-whisper (free)
  placeholder()  no audio at all: words spread at reading speed so a silent draft can be timed (free)
"""

from __future__ import annotations

import base64
import difflib
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from reels import config

API = "https://api.elevenlabs.io/v1"
# Premade voices every key can use.
VOICES = {
    "lily": "pFZP5JQG7iQjIQuC4Bku", "matilda": "XrExE9yKIg1WjnnlVkGX",
    "liam": "TX3LPaxmHKxFdv7VOQHJ", "rachel": "21m00Tcm4TlvDq8ikWAM",
    "adam": "pNInz6obpgDQGcFmaJgB", "brian": "nPczCjzI2devNBz1zQrb",
    "jessica": "cgSgspJ2msm6clMCkdW9", "charlie": "IKne3meq5aSn9XLyUdCD",
}
CACHE = config.CACHE_DIR / "voice"


def estimate(text: str) -> float:
    """Rough ElevenLabs cost in USD for this text."""
    return len(text) / 1000 * config.ELEVENLABS_USD_PER_1K_CHARS


def _to_wav(src: Path, dst: Path) -> None:
    subprocess.run([config.FFMPEG, "-loglevel", "error", "-y", "-i", str(src), "-vn", "-ac", "1",
                    "-ar", "48000", str(dst)], check=True)


def _save(project, audio: Path | None, words: list[dict]) -> list[dict]:
    if audio:
        _to_wav(audio, project.root / "voice.wav")
    else:
        (project.root / "voice.wav").unlink(missing_ok=True)
    project.write("words.json", words)
    end = words[-1]["end"] if words else 0
    print(f"[voice] {len(words)} words, {end:.1f}s" + ("" if audio else " (silent timing)"))
    return words


# ── ElevenLabs ──────────────────────────────────────────────────────────

def _words_from_alignment(al: dict) -> list[dict]:
    words, cur, s, e = [], "", None, None
    for ch, cs, ce in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "start": round(s, 3), "end": round(e, 3)})
            cur, s = "", None
            continue
        s = cs if s is None else s
        cur, e = cur + ch, ce
    if cur:
        words.append({"w": cur, "start": round(s, 3), "end": round(e, 3)})
    return words


def tts(project, text: str, voice: str = "lily", speed: float = 1.05) -> list[dict]:
    """PAID. Cached by (text, voice, speed) so re-renders never re-spend."""
    if not config.ELEVENLABS_KEY:
        raise RuntimeError("ELEVENLABS_APIKEY is not set")
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha1(f"{text}|{voice}|{speed}".encode()).hexdigest()[:12]
    mp3, meta = CACHE / f"{tag}.mp3", CACHE / f"{tag}.json"
    if not (mp3.exists() and meta.exists()):
        vid = VOICES.get(voice.lower(), voice)
        body = {"text": text, "model_id": config.ELEVENLABS_MODEL,
                "voice_settings": {"stability": 0.42, "similarity_boost": 0.78, "style": 0.4,
                                   "use_speaker_boost": True, "speed": speed}}
        req = urllib.request.Request(f"{API}/text-to-speech/{vid}/with-timestamps", data=json.dumps(body).encode(),
                                     headers={"xi-api-key": config.ELEVENLABS_KEY, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                j = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"ElevenLabs HTTP {e.code}: {e.read()[:300]!r}")
        mp3.write_bytes(base64.b64decode(j["audio_base64"]))
        meta.write_text(json.dumps(_words_from_alignment(j.get("normalized_alignment") or j["alignment"])))
    return _save(project, mp3, json.loads(meta.read_text()))


# ── local whisper ───────────────────────────────────────────────────────

def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


def _whisper(audio: Path, prompt: str = "") -> list[dict]:
    from faster_whisper import WhisperModel
    print("[voice] transcribing with whisper (local, free)...")
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = model.transcribe(str(audio), word_timestamps=True, initial_prompt=prompt[:800] or None)
    return [{"w": w.word.strip(), "start": round(w.start, 3), "end": round(w.end, 3)}
            for s in segs for w in (s.words or []) if w.word.strip()]


def _onto_script(heard: list[dict], script: str, dur: float) -> list[dict]:
    """Map whisper words onto the script's own tokens; interpolate the ones it missed."""
    toks = script.split()
    sm = difflib.SequenceMatcher(a=[_norm(t) for t in toks], b=[_norm(w["w"]) for w in heard], autojunk=False)
    times: list[tuple[float, float] | None] = [None] * len(toks)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            times[a + k] = (heard[b + k]["start"], heard[b + k]["end"])
    i = 0
    while i < len(toks):
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < len(toks) and times[j] is None:
            j += 1
        lo = times[i - 1][1] if i > 0 else 0.0
        hi = times[j][0] if j < len(toks) else dur
        step = (hi - lo) / (j - i + 1)
        for k in range(i, j):
            s = lo + step * (k - i + 0.5)
            times[k] = (round(s, 3), round(s + step * 0.8, 3))
        i = j
    return [{"w": t, "start": s, "end": e} for t, (s, e) in zip(toks, times)]


def from_audio(project, src: Path, script: str | None = None) -> list[dict]:
    """Your VO or a talking-head video. With a script, words follow the script's spelling."""
    from reels.assets.media import duration
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = hashlib.sha1(Path(src).read_bytes()[:4_000_000] + (script or "").encode()).hexdigest()[:12]
    meta = CACHE / f"whisper_{tag}.json"
    if meta.exists():
        words = json.loads(meta.read_text())
    else:
        heard = _whisper(Path(src), script or "")
        words = _onto_script(heard, script, duration(Path(src))) if script else heard
        meta.write_text(json.dumps(words))
    return _save(project, Path(src), words)


# ── silent draft ────────────────────────────────────────────────────────

def placeholder(project, text: str, wps: float = 2.7, start: float = 0.15) -> list[dict]:
    """Words at reading speed (longer words and sentence ends take longer). No audio."""
    words, t = [], start
    for tok in text.split():
        d = (0.18 + 0.045 * len(tok)) * 2.7 / wps
        words.append({"w": tok, "start": round(t, 3), "end": round(t + d * 0.85, 3)})
        t += d + (0.28 if re.search(r"[.!?]$", tok) else 0.12 if re.search(r"[,;:—]$", tok) else 0)
    return _save(project, None, words)
