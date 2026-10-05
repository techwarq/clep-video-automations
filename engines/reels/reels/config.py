"""Paths, keys and defaults. Everything can be overridden from .env or the environment."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # pipeline/
PACKAGE = ROOT / "reels"
SKILLS_DIR = ROOT / "skills"
LIBRARY = ROOT / "library"
FONTS_DIR = LIBRARY / "fonts"
SFX_DIR = LIBRARY / "sfx"
MUSIC_DIR = LIBRARY / "music"
PROJECTS_DIR = ROOT / "projects"
OUTPUT_DIR = ROOT / "output"
CACHE_DIR = ROOT / ".cache"


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_env()

# ── models (OpenRouter) ─────────────────────────────────────────────────
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("REELS_MODEL", "meta/muse-spark-1.3-contributor")
BUDGET_USD = float(os.environ.get("REELS_BUDGET_USD", "1.00"))

# ── voice ───────────────────────────────────────────────────────────────
ELEVENLABS_KEY = os.environ.get("ELEVENLABS_APIKEY") or os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")
# ElevenLabs bills per character; used for the cost estimate before any paid TTS call.
ELEVENLABS_USD_PER_1K_CHARS = float(os.environ.get("ELEVENLABS_USD_PER_1K_CHARS", "0.30"))


# ── tools ───────────────────────────────────────────────────────────────
def _bin(env: str, name: str) -> str:
    full = Path("/opt/homebrew/opt/ffmpeg-full/bin") / name
    return os.environ.get(env) or (str(full) if full.exists() else shutil.which(name) or name)


FFMPEG = _bin("REELS_FFMPEG", "ffmpeg")
FFPROBE = _bin("REELS_FFPROBE", "ffprobe")

# ── canvas ──────────────────────────────────────────────────────────────
W, H = 1080, 1920
FPS = 30

for d in (PROJECTS_DIR, OUTPUT_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)
