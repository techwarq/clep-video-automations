"""Plan assets -> real Pinterest footage in the project.

For each asset: search its queries, rank for a 9:16 reel (vertical, sharp, long
enough), let the vision model veto off-topic pins and ones with burned-in
text/watermarks (thumbnails only — cheap), download the best and extract frames.
`sheet()` makes numbered contact sheets for picking by eye instead.
"""

from __future__ import annotations

import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from reels import config, llm
from reels.assets import media, pinterest

DOWNLOADS = config.CACHE_DIR / "pinterest"


def _score(pin: dict, rank: int, kind: str, need_s: float) -> float:
    w, h = pin["width"] or 1, pin["height"] or 1
    ar = w / h
    s = 3.0 if ar <= 0.66 else 2.0 if ar <= 0.85 else 0.8 if ar <= 1.05 else 0.0
    s += 1.0 if min(w, h) >= 720 else 0.0
    s += (25 - min(rank, 25)) / 25 * 1.5
    if pin["kind"] == "video":
        s += 2.0 if kind == "video" else -1.5
        if pin["duration"] < need_s:
            s -= 3.0
    elif kind == "image":
        s += 2.5
    return s


def _pool(asset: dict) -> list[dict]:
    queries = [asset["query"]] + list(asset.get("alt") or [])
    scopes = ("videos", "pins") if asset.get("kind", "video") == "video" else ("pins", "videos")
    seen, pool = set(), []
    for q in queries:
        for scope in scopes:
            for rank, p in enumerate(pinterest.search(q, scope=scope, limit=25)):
                if p["id"] not in seen and min(p["width"], p["height"]) >= 480:
                    seen.add(p["id"])
                    pool.append({**p, "_rank": rank})
        if len(pool) >= 30:
            break
    need = float(asset.get("min_s", 3.0))
    pool.sort(key=lambda p: -_score(p, p["_rank"], asset.get("kind", "video"), need))
    return pool


def _thumb_url(pin: dict) -> str | None:
    try:
        r = pinterest.session().get(pin["thumb"], timeout=20)
        r.raise_for_status()
        return "data:image/jpeg;base64," + base64.b64encode(r.content).decode()
    except Exception:
        return None


def _screen(asset: dict, cands: list[dict], model: str | None) -> list[dict] | None:
    """Vision veto on thumbnails -> accepted pins best-first, or None if the model is unavailable."""
    if not config.OPENROUTER_API_KEY or not cands:
        return None
    rules = [
        "REJECT burned-in text, captions, subtitles, headlines, watermarks or channel logos added on top. "
        "Signs, screens and logos physically in the scene are fine.",
        "REJECT collages, split screens, grids, memes, article thumbnails, blurry or low quality shots.",
    ]
    if asset.get("subject"):
        rules.insert(0, f"The shot MUST clearly show {asset['subject']}. Reject anything else.")
    content = [llm.text_part(
        f"Footage for a vertical reel. Wanted: {asset.get('use') or asset['query']}.\n"
        + "\n".join("- " + r for r in rules)
        + f"\nJudge each of the {len(cands)} candidates. Return ONLY JSON "
          '{"shots": [{"i": 0, "ok": true, "score": 0-10}]} — score = fit + how cinematic.')]
    with ThreadPoolExecutor(8) as ex:   # the model can't fetch pinimg URLs itself: send the bytes
        thumbs = list(ex.map(_thumb_url, cands))
    cands = [c for c, u in zip(cands, thumbs) if u]
    thumbs = [u for u in thumbs if u]
    for i, (c, url) in enumerate(zip(cands, thumbs)):
        content.append(llm.text_part(f"#{i} ({c['kind']}) {c.get('title', '')[:80]!r}"))
        content.append({"type": "image_url", "image_url": {"url": url}})
    try:
        got = llm.chat_json([{"role": "user", "content": content}], tag=f"screen {asset['key']}",
                            model=model, max_tokens=3000, temperature=0.1)
    except Exception as e:
        print(f"[picker] vision screen unavailable ({str(e)[:120]}) — ranking only")
        return None
    ok = [(cands[x["i"]], float(x.get("score", 5))) for x in got.get("shots", [])
          if isinstance(x.get("i"), int) and 0 <= x["i"] < len(cands) and x.get("ok")]
    return [p for p, _ in sorted(ok, key=lambda t: -t[1])]


def fetch(project, asset: dict, used: set[str], vision: bool = True, model: str | None = None) -> dict | None:
    """Find, download and prepare one plan asset. Returns its media entry or None."""
    pool = [p for p in _pool(asset) if p["id"] not in used]
    if vision:
        screened = _screen(asset, pool[:12], model)
        if screened is not None:
            pool = screened + [p for p in pool[12:24]]   # unscreened tail only as a last resort
    for pin in pool[:8]:
        path = pinterest.download(pin, DOWNLOADS)
        info = media.probe(path) if path else None
        if not info or min(info["width"], info["height"]) < 360:
            continue
        if pin["kind"] == "video" and info["duration"] < float(asset.get("min_s", 1.5)):
            continue
        used.add(pin["id"])
        note = f"pin {pin['id']}: {pin.get('title', '')[:60]}".strip()
        return media.add(project, asset["key"], path, note=note)
    print(f"[picker] {asset['key']}: nothing usable for {asset['query']!r}")
    return None


def gather(project, assets: list[dict], vision: bool = True, model: str | None = None) -> dict:
    """Fetch every plan asset; an empty one borrows the topic-wide fallback query if given."""
    used: set[str] = set()
    for a in assets:
        if a["key"] in project.media:
            continue
        got = fetch(project, a, used, vision, model)
        if not got and a.get("fallback"):
            fetch(project, {**a, "query": a["fallback"], "alt": []}, used, vision=False)
    return project.media


# ── hand-picking ────────────────────────────────────────────────────────

def sheet(query: str, out_dir: Path, images: bool = False, n: int = 16) -> Path:
    """Numbered contact sheet + pins JSON for picking footage by eye."""
    from PIL import Image, ImageDraw, ImageFont
    pins = pinterest.search(query, "pins" if images else "videos", 40)
    pins = [p for p in pins if (p["kind"] == "image") == images and min(p["width"], p["height"]) >= 480][:n]

    def thumb(p):
        try:
            r = pinterest.session().get(p["thumb"], timeout=20)
            return Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception:
            return None

    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(thumb, pins))
    cw, ch = 220, 330
    img = Image.new("RGB", (cw * 8, ch * max(1, (len(pins) + 7) // 8)), (30, 30, 30))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=20)
    for i, (p, im) in enumerate(zip(pins, ims)):
        x, y = (i % 8) * cw, (i // 8) * ch
        if im:
            im.thumbnail((cw - 6, ch - 40))
            img.paste(im, (x + 3, y + 3))
        label = f"{i} {p['width']}x{p['height']}" + (f" {p['duration']:.0f}s" if p["kind"] == "video" else "")
        d.text((x + 6, y + ch - 30), label, font=font, fill=(255, 220, 0))
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "_".join(query.split())[:40]
    img.save(out_dir / f"{name}.jpg", quality=80)
    (out_dir / f"{name}.json").write_text(json.dumps(pins, indent=1))
    print(f"[picker] {len(pins)} candidates -> {out_dir / (name + '.jpg')}")
    return out_dir / f"{name}.jpg"


def pick(project, key: str, sheet_json: Path, index: int) -> dict:
    """Download pin #index from a contact sheet into the project as `key`."""
    pin = json.loads(Path(sheet_json).read_text())[index]
    path = pinterest.download(pin, DOWNLOADS)
    if not path:
        raise RuntimeError(f"download failed for pin {pin['id']}")
    return media.add(project, key, path, note=f"pin {pin['id']} (hand-picked)")
