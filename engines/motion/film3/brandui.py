"""Brand UI grounding: find real pictures of the product (site mockups, App Store screenshots, user uploads), let the
model pick the product-UI regions and the device, crop them, and MEASURE their colours in code.

Result: projects/<name>/film3/brand_ui.json + film3/refs/*.png (reference crops sent to every state call).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List

from PIL import Image

from . import llm

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
IMG = (".png", ".jpg", ".jpeg", ".webp")


def _get(url: str, timeout=30):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def app_store(name: str, domain: str, out: Path, n: int = 6) -> List[Path]:
    """Screenshots of the product's iOS app (free iTunes Search API). Matched by the site's domain or name."""
    root = domain.replace("www.", "").split(".")[-2] if domain.count(".") >= 1 else domain
    words = [w.lower() for w in re.findall(r"[a-zA-Z]{3,}", name or root)]
    for country in ("us", "in", "gb"):
        raw = _get(f"https://itunes.apple.com/search?term={urllib.parse.quote(name or root)}&entity=software&limit=8&country={country}")
        if not raw:
            continue
        for r in json.loads(raw).get("results", []):
            hay = " ".join(str(r.get(k, "")) for k in ("sellerUrl", "artistName", "trackName", "bundleId")).lower()
            if root.lower() in hay or (words and words[0] in hay):
                got = []
                for i, u in enumerate(r.get("screenshotUrls", [])[:n]):
                    big = re.sub(r"/\d+x\d+bb\.(jpg|png)$", "/1242x2688bb.jpg", u)
                    data = _get(big) or _get(u)
                    if data:
                        p = out / f"appstore_{i}.jpg"; p.write_bytes(data); got.append(p)
                return got
    return []


def gather(ctx: dict, work: Path) -> List[dict]:
    cand = work / "brand_ui" / "src"; cand.mkdir(parents=True, exist_ok=True)
    items = []
    user = ctx["project"].assets / "user"
    for p in sorted(user.rglob("*")) if user.exists() else []:
        if p.suffix.lower() in IMG and "music" not in p.name.lower():
            items.append({"path": p, "source": "user upload (the product's real UI — highest trust)"})
    for p in ctx["shots"][:5]:
        items.append({"path": p, "source": "product website page"})
    dom = urllib.parse.urlparse(ctx["url"]).netloc
    for p in app_store(ctx["intel"]["product"].get("name", ""), dom, cand):
        items.append({"path": p, "source": "App Store screenshot of the product's app"})
    return items[:12]


def palette(im: Image.Image, k: int = 8) -> list:
    """Dominant colours of a crop, measured (not guessed)."""
    small = im.convert("RGB").resize((160, int(160 * im.height / max(1, im.width))) if im.width > 160 else im.size)
    q = small.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: k * 3]; counts = sorted(q.getcolors(), reverse=True)
    tot = sum(c for c, _ in counts)
    return [{"hex": "#%02x%02x%02x" % tuple(pal[i * 3:i * 3 + 3]), "share": round(c / tot, 3)} for c, i in counts if c / tot > 0.01]


TASK = """# TASK: study the product's real UI
The images are numbered in the order given (image 0, image 1, …); each is labelled with its source.
Reply with ONLY JSON:
{"device": {"kind": "phone|desktop|browser|none", "theme": "light|dark", "why": "the evidence"},
 "surfaces": [{"img": 0, "box": [x0, y0, x1, y1], "name": "...", "anatomy": "top-to-bottom build description with sizes, colours, radii, badges, buttons"}],
 "ui_spec": {"overall": "how the product's UI looks in one paragraph", "type": "...", "radii": "...", "spacing": "...",
             "signature_details": ["the 3-6 details that make it instantly recognisable"], "icons": "...", "copy_voice": "...",
             "dont": ["things that would make it look generic or wrong"]}}
Boxes are fractions 0–1 of that image, tight around ONE product surface (not the marketing page). 3–8 surfaces, best first."""


def study(ctx: dict, work: Path) -> dict:
    items = gather(ctx, work)
    content = [{"type": "text", "text": f"PRODUCT\n{json.dumps(ctx['intel']['product'].get('one_liner'))} · {ctx['url']}\n\nIMAGES:"}]
    for i, it in enumerate(items):
        content += [{"type": "text", "text": f"image {i}: {it['source']}"}, llm.image_part(it["path"], max_w=1400)]
    sk = Path(__file__).resolve().parent / "skills"
    sys = "\n\n".join((sk / n).read_text() for n in ("07_brand_ui.md", "03_design.md")) + "\n\n" + TASK
    res = llm.json_([{"role": "system", "content": sys}, {"role": "user", "content": content}], tag="brand-ui", temperature=0.2, max_tokens=12000)
    refs = work / "refs"; refs.mkdir(parents=True, exist_ok=True)
    for f in refs.glob("*.png"):
        f.unlink()
    kept = []
    for j, s in enumerate(res.get("surfaces", [])[:8]):
        try:
            im = Image.open(items[int(s["img"])]["path"]).convert("RGB")
            x0, y0, x1, y1 = [float(v) for v in s["box"]]
            if max(x0, y0, x1, y1) > 1.5:                       # model gave pixels: normalise
                x0, x1, y0, y1 = x0 / im.width, x1 / im.width, y0 / im.height, y1 / im.height
            pad = 0.01
            box = (int(max(0, x0 - pad) * im.width), int(max(0, y0 - pad) * im.height), int(min(1, x1 + pad) * im.width), int(min(1, y1 + pad) * im.height))
            if box[2] - box[0] < 40 or box[3] - box[1] < 30:
                continue
            crop = im.crop(box)
            name = re.sub(r"[^a-z0-9]+", "_", s.get("name", f"surface{j}").lower()).strip("_")[:40]
            dest = refs / f"{j}_{name}.png"; crop.save(dest)
            kept.append({**s, "file": str(dest), "palette": palette(crop), "source": items[int(s["img"])]["source"]})
        except Exception as e:
            print(f"[brand-ui] surface {j}: {e}")
    res["surfaces"] = kept
    res["measured_palette"] = palette(Image.open(kept[0]["file"])) if kept else []
    (work / "brand_ui.json").write_text(json.dumps(res, indent=1))
    print(f"[brand-ui] device {res.get('device', {}).get('kind')} · {len(kept)} surfaces · {[k['name'] for k in kept]}")
    return res


def text(bu: dict) -> str:
    """Compact brand-UI brief for prompts."""
    if not bu:
        return "BRAND UI: (no product UI found — derive from the design system)"
    s = [f"- {x['name']}: {x.get('anatomy', '')} · measured colours {[p['hex'] for p in x.get('palette', [])[:6]]}" for x in bu.get("surfaces", [])]
    return (f"BRAND UI (the product's REAL UI — rebuild it exactly)\ndevice: {json.dumps(bu.get('device'))}\n"
            f"spec: {json.dumps(bu.get('ui_spec'), indent=1)}\nsurfaces:\n" + "\n".join(s))


def ref_images(bu: dict, n: int = 3, prefer: str = "") -> list:
    sur = bu.get("surfaces", []) if bu else []
    if prefer:
        words = set(re.findall(r"[a-z]+", prefer.lower()))
        sur = sorted(sur, key=lambda x: -len(words & set(re.findall(r"[a-z]+", (x["name"] + " " + x.get("anatomy", "")).lower()))))
    return [llm.image_part(Path(x["file"]), max_w=900) for x in sur[:n] if Path(x["file"]).exists()]
