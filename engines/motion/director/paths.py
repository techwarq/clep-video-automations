"""Filesystem layout + env loading shared by every director module."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # pipeline_motion/
ENGINE = ROOT / "engine"                               # Remotion + GSAP renderer
PROJECTS = ROOT / "projects"                           # one folder per video project
REGISTRY_JSON = ENGINE / "registry.json"               # scene/style contract exported by the engine


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        os.environ.setdefault(k, v)


# pipeline_motion/.env wins, then the shared engines/reels/.env (OPENROUTER_API_KEY lives there).
_load_dotenv(ROOT / ".env")
_load_dotenv(ROOT.parent / "reels" / ".env")


class Project:
    """projects/<name>/ — everything one video needs, self-contained.

        brand.json        brand kit extracted from the site (+ user edits)
        script.txt        the script / braindump
        reference.txt     named reference style / notes (optional)
        assets/           everything the renderer can load (served as Remotion's public dir)
          shots/          website screenshots
          brand/          logo, icon
          fonts/          font files pulled from the site
          user/           your own logo, screenshots, footage, music, voiceover
        specs/            storyboard variants + note revisions (VideoSpec JSON)
        stills/<spec>/    one still per scene + contact sheet
        renders/          final mp4s
    """

    def __init__(self, name: str):
        self.name = name
        self.dir = PROJECTS / name

    @property
    def assets(self) -> Path:
        return self.dir / "assets"

    @property
    def specs(self) -> Path:
        return self.dir / "specs"

    @property
    def brand_path(self) -> Path:
        return self.dir / "brand.json"

    def ensure(self) -> "Project":
        for d in (self.assets / "shots", self.assets / "brand", self.assets / "fonts", self.assets / "user", self.specs,
                  self.dir / "stills", self.dir / "renders"):
            d.mkdir(parents=True, exist_ok=True)
        return self

    def spec_path(self, spec: str) -> Path:
        p = Path(spec)
        if p.exists():
            return p
        if not spec.endswith(".json"):
            spec += ".json"
        return self.specs / spec

    def read(self, rel: str, default: str = "") -> str:
        p = self.dir / rel
        return p.read_text() if p.exists() else default
