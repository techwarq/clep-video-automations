"""Real logos for the tools a video mentions (Slack, GitHub, Shopify, Instagram…).

Resolution order for an app name, best first:
  1. SVGL        full-color SVGs of ~700 tech/SaaS brands (svgl.app)
  2. Simple Icons single-color glyphs + official hex for ~3,400 brands (npm simple-icons, CC0)
  3. direct      a vetted vector file for big brands both libraries dropped (Amazon)
  4. site icon   the company's own apple-touch/manifest icon, only if ≥ 128px
  5. nothing     the engine draws a neutral letter tile — never a wrong or made-up logo

Files are cached in logos/cache/ and copied into the project as assets/apps/<slug>.<ext>, so a spec only
ever references project files. `catalog()` is the list shown to the director and via `motion.py logos`.
Logos are trademarks of their owners; they're used here the way launch videos show integrations.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

from .paths import ROOT

CACHE = ROOT / "logos" / "cache"
SI_DIR = ROOT / "engine" / "node_modules" / "simple-icons"
SVGL_API = "https://api.svgl.app"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/128 Safari/537.36"}

# How people write a tool → the name the libraries use. Only entries where plain normalizing isn't enough.
ALIASES = {
    "meta ads": "meta", "facebook ads": "facebook", "fb": "facebook", "ig": "instagram", "twitter": "x", "x.com": "x",
    "google sheets": "google sheets", "sheets": "google sheets", "gsheets": "google sheets", "google docs": "google docs",
    "google drive": "google drive", "gdrive": "google drive", "google calendar": "google calendar", "calendar": "google calendar",
    "google ads": "google ads", "ga4": "google analytics", "google analytics": "google analytics", "gmail": "gmail",
    "teams": "microsoft teams", "ms teams": "microsoft teams", "excel": "microsoft excel", "word": "microsoft word",
    "outlook": "microsoft outlook", "aws": "amazon web services", "chatgpt": "openai", "gpt": "openai",
    "claude": "claude", "gemini": "google gemini", "vscode": "visual studio code", "vs code": "visual studio code",
    "quickbooks": "quickbooks", "qbo": "quickbooks", "amazon seller central": "amazon", "fba": "amazon",
    "monday": "monday.com", "cal": "cal.com", "loom": "loom", "hubspot crm": "hubspot",
}
# Vector files for big brands both libraries dropped and whose sites block icon requests.
DIRECT = {
    "amazon": "https://upload.wikimedia.org/wikipedia/commons/4/4a/Amazon_icon.svg",
}
# Company domains for the site-icon fallback (brands both libraries lack).
DOMAINS = {
    "amazon": "amazon.com", "microsoft outlook": "outlook.com", "klaviyo": "klaviyo.com", "monday.com": "monday.com",
    "ramp": "ramp.com", "mercury": "mercury.com", "rippling": "rippling.com", "docusign": "docusign.com",
    "brex": "brex.com", "gusto": "gusto.com", "deel": "deel.com", "attio": "attio.com", "granola": "granola.ai",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "app"


def _get(url: str, limit: int = 4_000_000) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12).read(limit)


# ---------------------------------------------------------------- sources

_si: Optional[Dict[str, dict]] = None
_svgl: Optional[Dict[str, dict]] = None


def _simple_icons() -> Dict[str, dict]:
    """normalized title/slug/aka → {title, slug, hex}"""
    global _si
    if _si is None:
        _si = {}
        p = SI_DIR / "data" / "simple-icons.json"
        if p.exists():
            data = json.loads(p.read_text())
            for x in data if isinstance(data, list) else data.get("icons", []):
                slug = x.get("slug") or _norm(x["title"])
                entry = {"title": x["title"], "slug": slug, "hex": "#" + x["hex"]}
                for key in [x["title"], slug] + list((x.get("aliases") or {}).get("aka") or []):
                    _si.setdefault(_norm(key), entry)
    return _si


def _svgl_index() -> Dict[str, dict]:
    """normalized title → svgl entry (list fetched once, cached on disk)."""
    global _svgl
    if _svgl is None:
        p = CACHE / "svgl.json"
        if not p.exists():
            try:
                CACHE.mkdir(parents=True, exist_ok=True)
                p.write_bytes(_get(SVGL_API))
            except Exception as e:
                print(f"[logos] svgl list unavailable: {e}")
        try:
            rows = json.loads(p.read_text()) if p.exists() else []
        except Exception:
            rows = []
        _svgl = {}
        for r in rows:
            _svgl.setdefault(_norm(r.get("title", "")), r)
    return _svgl


def _svgl_file(entry: dict, dark: bool) -> Optional[Path]:
    route = entry.get("route")
    if isinstance(route, dict):  # {light, dark}: "light" is the logo drawn for light backgrounds
        route = route.get("dark" if dark else "light") or next(iter(route.values()))
    if not isinstance(route, str):
        return None
    dest = CACHE / "svgl" / Path(route).name
    if not dest.exists():
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_get(route))
        except Exception:
            return None
    return dest


def _site_icon(domain: str) -> Optional[Path]:
    """Largest raster app icon the company's site serves, if it's big enough to look sharp (≥128px)."""
    from PIL import Image
    dest = CACHE / "site" / f"{_slug(domain)}.png"
    if dest.exists():
        return dest
    base = f"https://{domain}/"
    urls: List[str] = []
    try:
        html = _get(base).decode("utf-8", "ignore")
        for tag in re.findall(r"<link[^>]+>", html, re.I):
            rel = (re.search(r'rel=["\']([^"\']+)', tag, re.I) or [None, ""])[1].lower()
            href = (re.search(r'href=["\']([^"\']+)', tag, re.I) or [None, None])[1]
            if href and "icon" in rel:
                urls.append(urljoin(base, href))
            if href and "manifest" in rel:
                try:
                    m = json.loads(_get(urljoin(base, href)))
                    urls += [urljoin(urljoin(base, href), i["src"]) for i in m.get("icons", []) if i.get("src")]
                except Exception:
                    pass
    except Exception:
        pass
    urls += [base + "apple-touch-icon.png"]
    best = None
    for u in dict.fromkeys(urls):
        if u.lower().split("?")[0].endswith(".svg"):
            continue
        try:
            im = Image.open(io.BytesIO(_get(u)))
            if not best or min(im.size) > min(best.size):
                best = im.convert("RGBA")
        except Exception:
            continue
    if not best or min(best.size) < 128:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    best.save(dest)
    return dest


# ---------------------------------------------------------------- resolve

def lookup(app: str) -> Optional[dict]:
    """What we'd use for this name, without downloading: {title, source, hex?}."""
    key = ALIASES.get((app or "").strip().lower(), app or "")
    n = _norm(key)
    if not n:
        return None
    if n in _svgl_index():
        return {"title": _svgl_index()[n]["title"], "source": "svgl"}
    if n in _simple_icons():
        e = _simple_icons()[n]
        return {"title": e["title"], "source": "simple-icons", "hex": e["hex"]}
    if key.lower() in DIRECT:
        return {"title": key.title(), "source": "direct", "url": DIRECT[key.lower()]}
    if key.lower() in DOMAINS:
        return {"title": key, "source": "site", "domain": DOMAINS[key.lower()]}
    return None


def resolve(app: str, assets_dir: Path, dark: bool = False) -> Optional[dict]:
    """App name → a logo copied into the project: {src: 'apps/x.svg', mode: 'color'|'glyph', color?}. None = no real logo."""
    hit = lookup(app)
    if not hit:
        return None
    key = _norm(ALIASES.get(app.strip().lower(), app))
    out_dir = Path(assets_dir) / "apps"
    src: Optional[Path] = None
    info: dict = {}
    if hit["source"] == "svgl":
        src = _svgl_file(_svgl_index()[key], dark)
        info = {"mode": "color"}
    if not src and key in _simple_icons():
        e = _simple_icons()[key]
        f = SI_DIR / "icons" / f"{e['slug']}.svg"
        if f.exists():
            src, info = f, {"mode": "glyph", "color": e["hex"]}
    if not src and hit["source"] == "direct":
        f = CACHE / "direct" / Path(hit["url"]).name
        try:
            if not f.exists():
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(_get(hit["url"]))
            src, info = f, {"mode": "color"}
        except Exception:
            src = None
    if not src and hit["source"] == "site":
        src = _site_icon(hit["domain"])
        info = {"mode": "color"}
    if not src:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{_slug(hit['title'])}{'-dark' if dark and info['mode'] == 'color' else ''}{src.suffix}"
    if not dest.exists():
        shutil.copyfile(src, dest)
    return {"src": f"apps/{dest.name}", **info, "title": hit["title"]}


def catalog(query: str = "") -> List[dict]:
    """Every logo we can show, merged across sources (SVGL first). Filter with a query."""
    seen, rows = set(), []
    for n, r in _svgl_index().items():
        seen.add(n)
        rows.append({"title": r["title"], "source": "svgl", "category": r.get("category")})
    for n, e in _simple_icons().items():
        if _norm(e["title"]) not in seen and n == _norm(e["title"]):
            seen.add(n)
            rows.append({"title": e["title"], "source": "simple-icons", "hex": e["hex"]})
    for k in list(DIRECT) + list(DOMAINS):
        if _norm(k) not in seen:
            seen.add(_norm(k))
            rows.append({"title": k, "source": "site"})
    q = query.lower().strip()
    return sorted([r for r in rows if not q or q in r["title"].lower()], key=lambda r: r["title"].lower())


# The everyday tools a launch story names — shown to the director so it writes real app names.
COMMON = ["Slack", "Gmail", "Google Sheets", "Google Calendar", "Notion", "Linear", "Jira", "GitHub", "Figma", "Zoom",
          "Loom", "Intercom", "Zendesk", "HubSpot", "Salesforce", "Stripe", "QuickBooks", "Xero", "Shopify", "Amazon",
          "Meta", "Instagram", "TikTok", "YouTube", "X", "LinkedIn", "WhatsApp", "Discord", "Microsoft Teams",
          "Microsoft Excel", "Airtable", "Asana", "Trello", "ClickUp", "Mixpanel", "Google Analytics", "Google Ads",
          "Klaviyo", "Mailchimp", "Calendly", "Dropbox", "Google Drive", "OpenAI", "Claude", "Vercel", "Sentry"]
