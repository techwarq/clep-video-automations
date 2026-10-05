"""Catch broken compositions before a full render.

lint()   static rules any model tends to break (timers, CSS animation, <video>, unknown media keys)
smoke()  load the page, seek across the reel, collect JS errors, slow frames, blank frames
stills() review frames at chosen times
Each returns plain-language problems a model can fix.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from reels.render.browser import open_page

BANNED = [
    (r"\bsetTimeout\s*\(|\bsetInterval\s*\(|requestAnimationFrame", "uses timers/rAF — draw everything from t inside R.scene"),
    (r"Math\.random\s*\(", "uses Math.random — use R.hash(i) so every frame is reproducible"),
    (r"Date\.now|performance\.now|new Date\(", "reads the clock — time only comes from t"),
    (r"<video\b|<audio\b", "uses <video>/<audio> — footage is <img> + R.show, sound is R.sfx/R.music/R.clipAudio"),
    (r"@keyframes|\banimation\s*:", "uses CSS animation — animate from t in R.scene instead"),
    (r"\btransition\s*:\s*(?!none)", "uses CSS transition — animate from t in R.scene instead"),
    (r"https?://(?!www\.w3\.org)", "loads something from the internet — use only local media keys and listed fonts"),
]
REQUIRED = [
    (r"<script[^>]+src=[\"']data\.js[\"']", 'missing <script src="data.js"></script> in <head>'),
    (r"<script[^>]+src=[\"']runtime\.js[\"']", 'missing <script src="runtime.js"></script> after data.js'),
    (r"R\.scene\s*\(", "never calls R.scene(t => ...) — nothing will move"),
]


def lint(html: str, media: dict) -> list[str]:
    problems = [msg for pat, msg in BANNED if re.search(pat, html)]
    problems += [msg for pat, msg in REQUIRED if not re.search(pat, html)]
    d, r = html.find("data.js"), html.find("runtime.js")
    if d > r > -1:
        problems.append("data.js must load before runtime.js")
    keys = set(re.findall(r"R\.show\(\s*[^,]+?,\s*['\"]([\w-]+)['\"]", html))
    keys |= set(re.findall(r"R\.(?:frame|clipAudio)\(\s*['\"]([\w-]+)['\"]", html))
    for key in keys:
        if key not in media:
            problems.append(f'media key "{key}" does not exist (have: {", ".join(media) or "none"})')
    if re.search(r"R\.sfx\([^)]*\)", _scene_bodies(html)):
        problems.append("R.sfx is called inside R.scene — declare sound cues once at top level")
    return problems


def _scene_bodies(html: str) -> str:
    """Rough text of everything inside R.scene(...) callbacks."""
    out, i = [], 0
    while (i := html.find("R.scene(", i)) != -1:
        depth, j = 0, i + len("R.scene")
        while j < len(html):
            depth += {"(": 1, ")": -1}.get(html[j], 0)
            j += 1
            if depth == 0:
                break
        out.append(html[i:j])
        i = j
    return "\n".join(out)


def smoke(html_path: Path, dur: float, samples: int = 12) -> list[str]:
    problems: list[str] = []
    times = [dur * (k + 0.5) / samples for k in range(samples)]
    try:
        with open_page(html_path) as page:
            errs = page.errors()
            if errs:
                problems += [f"on load: {e}" for e in errs[:5]]
            slow, blank = [], []
            for t in times:
                t0 = time.time()
                try:
                    page.seek(t)
                except Exception as e:
                    problems.append(f"seek({t:.2f}) threw: {str(e).splitlines()[0][:200]}")
                    continue
                ms = (time.time() - t0) * 1000
                if ms > 400:
                    slow.append(f"{t:.1f}s={ms:.0f}ms")
                if _is_blank(page.jpeg(60)):
                    blank.append(f"{t:.1f}s")
                problems += [f"at {t:.2f}s: {e}" for e in page.errors()[:3]]
            if slow:
                problems.append("slow frames (keep each seek under 400 ms): " + ", ".join(slow[:5]))
            if len(blank) > samples // 3:
                problems.append("frame is a flat single colour at " + ", ".join(blank) +
                                " — something should always be on screen")
    except Exception as e:
        problems.append(f"page failed to load: {str(e).splitlines()[0][:300]}")
    return problems


def _is_blank(jpeg: bytes) -> bool:
    import io
    from PIL import Image, ImageStat
    im = Image.open(io.BytesIO(jpeg)).convert("L").resize((54, 96))
    return ImageStat.Stat(im).stddev[0] < 2.0


def stills(html_path: Path, times: list[float], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    files = []
    with open_page(html_path) as page:
        for t in times:
            files.append(page.still(t, out_dir / f"t{t:06.2f}.jpg"))
    return files


def contact_sheet(files: list[Path], out: Path, cols: int = 6) -> Path:
    from PIL import Image, ImageDraw
    w, h = 270, 480
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * (h + 28)), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        x, y = (i % cols) * w, (i // cols) * (h + 28)
        sheet.paste(Image.open(f).resize((w, h)), (x, y))
        d.text((x + 8, y + h + 6), f.stem, fill=(255, 220, 0))
    sheet.save(out, quality=85)
    return out
