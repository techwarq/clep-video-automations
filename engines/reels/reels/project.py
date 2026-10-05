"""One reel = one folder under projects/<slug>/.

    plan.json      what the director decided (style, beats, assets, music)
    words.json     spoken words with timings (empty for silent reels)
    data.js        window.REEL = {...}: timing, words, beats, media, fonts — what the HTML reads
    runtime.js     the engine runtime (copied in, so the folder renders on its own)
    comp.html      the composition (written by a model or by hand)
    media/         pre-extracted footage frames + stills, keyed like plan assets
    raw/           original downloads (clip audio comes from here)
    stills/        review frames
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from reels import config


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:48] or "reel"


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        for d in ("media", "raw", "stills"):
            (self.root / d).mkdir(parents=True, exist_ok=True)

    @classmethod
    def new(cls, name: str) -> "Project":
        root = config.PROJECTS_DIR / slug(name)
        n = 2
        while root.exists() and any(root.iterdir()):
            root = config.PROJECTS_DIR / f"{slug(name)}_{n}"
            n += 1
        return cls(root)

    # ── files ───────────────────────────────────────────────────────────
    @property
    def html(self) -> Path:
        return self.root / "comp.html"

    def read(self, name: str, default=None):
        p = self.root / name
        return json.loads(p.read_text()) if p.exists() else default

    def write(self, name: str, obj) -> Path:
        p = self.root / name
        p.write_text(json.dumps(obj, indent=2))
        return p

    @property
    def plan(self) -> dict:
        return self.read("plan.json", {})

    @property
    def words(self) -> list[dict]:
        return self.read("words.json", [])

    @property
    def media(self) -> dict:
        return self.read("media.json", {})

    # ── engine data ─────────────────────────────────────────────────────
    def install_runtime(self) -> None:
        shutil.copy(config.PACKAGE / "render" / "runtime.js", self.root / "runtime.js")
        fonts = self.root / "fonts"
        fonts.mkdir(exist_ok=True)
        for f in config.FONTS_DIR.glob("*.ttf"):
            if not (fonts / f.name).exists():
                shutil.copy(f, fonts / f.name)

    def fonts(self) -> list[dict]:
        out = []
        for f in sorted((self.root / "fonts").glob("*.ttf")):
            family = re.sub(r"(?<!^)(?=[A-Z])", " ", f.stem.split("-")[0])   # InstrumentSerif -> Instrument Serif
            out.append({"family": family, "url": f"fonts/{f.name}",
                        "style": "italic" if "Italic" in f.stem else "normal"})
        return out

    def timing(self) -> tuple[list[dict], float]:
        """Beat windows from word timings (narrated) or from each beat's dur (silent)."""
        plan, words = self.plan, self.words
        beats, t, i = [], 0.0, 0
        for k, b in enumerate(plan.get("beats", [])):
            n = len((b.get("text") or "").split())
            if words and n:
                j = min(i + n, len(words))
                t0 = 0.0 if not beats else words[min(i, len(words) - 1)]["start"] - 0.06
                beats.append({"id": b.get("id") or f"b{k + 1}", "t0": max(0.0, t0),
                              "w0": i, "w1": j, "text": b.get("text", "")})
                i = j
            else:
                d = float(b.get("dur") or 2.0)
                t0 = max(t, words[i - 1]["end"] + 0.1) if words and i else t
                beats.append({"id": b.get("id") or f"b{k + 1}", "t0": t0, "w0": i, "w1": i,
                              "text": b.get("text", ""), "dur": d})
            t = beats[-1]["t0"] + (beats[-1].get("dur") or 0)
        tail = float(plan.get("tail", 0.6))
        end = max([w["end"] for w in words] + [t, float(plan.get("seconds") or 0) if not words else 0]) + tail
        for a, b in zip(beats, beats[1:]):
            a["t1"] = b["t0"]
        if beats:
            beats[-1]["t1"] = end
        for b in beats:
            b["t0"], b["t1"] = round(b["t0"], 3), round(b["t1"], 3)
            b.pop("dur", None)
        return beats, round(end, 3)

    def write_data(self) -> dict:
        beats, dur = self.timing()
        reel = {"w": config.W, "h": config.H, "fps": config.FPS, "dur": dur,
                "title": self.plan.get("title", ""), "beats": beats, "words": self.words,
                "media": {k: {x: v[x] for x in v if x != "path"} for k, v in self.media.items()},
                "fonts": self.fonts(), "voice": (self.root / "voice.wav").exists()}
        (self.root / "data.js").write_text("window.REEL = " + json.dumps(reel) + ";\n")
        return reel

    def summary(self) -> str:
        """Plain-text brief of the timing and media for a model writing comp.html."""
        reel = self.write_data()
        lines = [f"Duration {reel['dur']}s at {reel['fps']} fps, canvas {reel['w']}x{reel['h']}.",
                 f"Voiceover: {'yes (voice.wav plays automatically)' if reel['voice'] else 'none'}.", "", "BEATS (R.beat(id)):"]
        for b in reel["beats"]:
            lines.append(f"- {b['id']}: {b['t0']:.2f}-{b['t1']:.2f}s  words[{b['w0']}:{b['w1']}]  \"{b['text']}\"")
        if reel["words"]:
            lines += ["", "WORDS (index: word @start-end):",
                      " ".join(f"{i}:{w['w']}@{w['start']:.2f}" for i, w in enumerate(reel["words"]))]
        lines += ["", "MEDIA (R.show(img, key, localSeconds)):"]
        for k, m in reel["media"].items():
            what = f"video {m['dur']:.1f}s" if m["kind"] == "video" else "image"
            lines.append(f"- {k}: {what} {m['w']}x{m['h']}  {m.get('note', '')}".rstrip())
        lines += ["", "FONTS: " + ", ".join(sorted({f['family'] for f in reel['fonts']})) +
                  " (plus system: Avenir Next, Helvetica Neue, Arial Black, Arial Rounded MT Bold, Futura, Georgia, Menlo)"]
        return "\n".join(lines)
