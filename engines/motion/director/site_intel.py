"""Website → site intelligence: the product's design system, its real components, and what it does.

brand.py gets the basics (colors, font files, logo PNG, screenshots). This goes further, free and local
(Playwright only, no scraping APIs), so every film can be built from the product's own world:

  design     type scale, spacing rhythm, radii, shadows, borders, gradients, CSS variables, icon style
  components the site's real buttons / cards / inputs / nav / pills, as computed styles + cut-out PNGs
  logo.svg   the vector logo (inline SVG with computed colours baked in, or the .svg file it serves)
  pages      5–10 key pages crawled (features, product, pricing, solutions, docs) → text + hero shots
  product    Muse Spark 1.3 reads all of it and writes the product model: what it does, for whom,
             its objects and actions, the aha, proof, the UI surfaces it has, a motion personality —
             plus the few questions it couldn't answer and the assets it still needs from the user.

Writes projects/<name>/intel.json and assets/intel/.

    python3 -m director.site_intel <project> <url> [--pages 8] [--model meta/muse-spark-1.3-contributor]
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from .paths import Project

VIEWPORT = {"width": 1440, "height": 900}
MODEL = os.environ.get("MOTION_INTEL_MODEL", "meta/muse-spark-1.3-contributor")

# Pages that explain the product, best first. Anything matching SKIP is never crawled.
PAGE_HINTS = ["product", "feature", "solution", "how-it-works", "platform", "use-case", "usecase", "pricing",
              "customer", "case-stud", "integration", "api", "docs", "about", "why", "business", "enterprise",
              "verified", "caller-id", "messaging", "ads", "overview"]
SKIP = re.compile(r"(login|signin|sign-in|signup|sign-up|register|privacy|terms|cookie|legal|careers|jobs|"
                  r"press|blog/|news/|status|contact-sales|\.pdf$|mailto:|tel:|#)", re.I)

DESIGN_JS = r"""
() => {
  const px = (v) => { const n = parseFloat(v); return isNaN(n) ? null : Math.round(n * 10) / 10; };
  const hex = (c) => {
    const m = c && c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const [r,g,b,a=1] = m[1].split(',').map(s=>parseFloat(s)); if (a < 0.05) return null;
    const h = '#' + [r,g,b].map(v=>Math.round(v).toString(16).padStart(2,'0')).join('');
    return a < 0.98 ? h + Math.round(a*255).toString(16).padStart(2,'0') : h;
  };
  const vis = (el) => {
    const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.1;
  };
  const ownText = (el) => Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ').trim();
  const all = Array.from(document.querySelectorAll('body *')).slice(0, 6000).filter(vis);

  // CSS custom properties declared on :root/html/body — often the site's actual design tokens.
  const vars = {};
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { continue; }
    for (const r of rules || []) {
      if (!r.style || !/^(:root|html|body|\.light|\[data-theme)/.test(r.selectorText || '')) continue;
      for (const p of r.style) if (p.startsWith('--') && Object.keys(vars).length < 200)
        vars[p] = r.style.getPropertyValue(p).trim().slice(0, 80);
    }
  }

  // Type scale: every distinct (size, weight, family) that carries real text, weighted by text length.
  const type = {};
  for (const el of all) {
    const t = ownText(el); if (t.length < 2) continue;
    const s = getComputedStyle(el);
    const key = [px(s.fontSize), s.fontWeight, s.fontFamily.split(',')[0].replace(/["']/g,'').trim()].join('|');
    const e = type[key] || (type[key] = { size: px(s.fontSize), weight: s.fontWeight,
      family: s.fontFamily.split(',')[0].replace(/["']/g,'').trim(), lineHeight: s.lineHeight,
      letterSpacing: s.letterSpacing, transform: s.textTransform, color: hex(s.color), chars: 0, tags: {}, sample: t.slice(0, 60) });
    e.chars += t.length; e.tags[el.tagName] = (e.tags[el.tagName] || 0) + 1;
  }

  const tally = (fn) => { const c = {}; for (const el of all) { const v = fn(el, getComputedStyle(el)); if (v != null && v !== '') c[v] = (c[v] || 0) + 1; } return Object.entries(c).sort((a,b)=>b[1]-a[1]); };
  const sp = {};
  for (const el of all) { const s = getComputedStyle(el);
    for (const p of ['paddingTop','paddingLeft','marginBottom','gap','rowGap']) { const v = px(s[p]); if (v && v >= 2 && v <= 200) sp[v] = (sp[v] || 0) + 1; } }
  const radii = tally((el, s) => { const v = px(s.borderTopLeftRadius); return v && v > 0 ? (v > 500 ? 'pill' : v) : null; });
  const shadows = tally((el, s) => s.boxShadow !== 'none' ? s.boxShadow : null).slice(0, 6);
  const borders = tally((el, s) => { const w = px(s.borderTopWidth); return w && s.borderTopStyle !== 'none' ? w + 'px ' + hex(s.borderTopColor) : null; }).slice(0, 6);
  const gradients = tally((el, s) => s.backgroundImage.includes('gradient') ? s.backgroundImage.slice(0, 240) : null).slice(0, 6);
  const blur = tally((el, s) => (s.backdropFilter && s.backdropFilter !== 'none') ? s.backdropFilter : null).slice(0, 4);

  // Icon style: inline SVGs drawn with strokes (outline icons) vs fills (solid icons).
  let stroke = 0, fill = 0;
  for (const svg of document.querySelectorAll('svg')) {
    const r = svg.getBoundingClientRect(); if (r.width < 10 || r.width > 64) continue;
    const p = svg.querySelector('path, circle, rect, line'); if (!p) continue;
    const s = getComputedStyle(p);
    if (s.stroke && s.stroke !== 'none' && (s.fill === 'none' || s.fill === 'rgba(0, 0, 0, 0)')) stroke++; else fill++;
  }

  // Representative components: tag the best example of each kind so Python can screenshot it.
  const style = (el) => { const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return { bg: hex(s.backgroundColor), color: hex(s.color), radius: s.borderRadius, padding: s.padding,
      border: s.borderTopWidth + ' ' + s.borderTopStyle + ' ' + hex(s.borderTopColor), shadow: s.boxShadow,
      font: s.fontSize + ' ' + s.fontWeight + ' ' + s.fontFamily.split(',')[0], backdrop: s.backdropFilter,
      w: Math.round(r.width), h: Math.round(r.height), text: (el.innerText || '').trim().replace(/\s+/g,' ').slice(0, 80) }; };
  const pick = (id, sel, ok, score) => {
    const cands = Array.from(document.querySelectorAll(sel)).filter(e => vis(e) && ok(e.getBoundingClientRect(), getComputedStyle(e), e));
    if (!cands.length) return null;
    cands.sort((a, b) => score(b) - score(a));
    cands[0].setAttribute('data-intel', id);
    return { id, ...style(cands[0]) };
  };
  const top = (e) => -e.getBoundingClientRect().top / 1000;
  const components = [
    pick('button_primary', 'button, a[class*=btn i], a[class*=button i], [role=button]',
      (r, s) => r.width > 60 && r.height > 28 && r.height < 90 && hex(s.backgroundColor), (e) => top(e) + (hex(getComputedStyle(e).backgroundColor) ? 1 : 0)),
    pick('button_secondary', 'button, a[class*=btn i], a[class*=button i], [role=button]',
      (r, s, e) => r.width > 60 && r.height > 28 && r.height < 90 && !e.hasAttribute('data-intel') && (!hex(s.backgroundColor) || parseFloat(s.borderTopWidth) > 0), top),
    pick('card', '[class*=card i], article, li, [class*=tile i], [class*=feature i]',
      (r, s) => r.width > 220 && r.width < 700 && r.height > 140 && r.height < 800 && (hex(s.backgroundColor) || s.boxShadow !== 'none' || parseFloat(s.borderTopWidth) > 0),
      (e) => (getComputedStyle(e).boxShadow !== 'none' ? 1 : 0) + top(e) * 0.2),
    pick('input', 'input[type=text], input[type=email], input[type=search], input:not([type]), textarea, select',
      (r) => r.width > 120 && r.height > 24, top),
    pick('nav', 'header, nav', (r) => r.width > 800 && r.height > 30 && r.height < 160 && r.top < 120, (e) => -e.getBoundingClientRect().top),
    pick('pill', '[class*=badge i], [class*=pill i], [class*=tag i], [class*=chip i], [class*=eyebrow i]',
      (r, s) => r.width > 30 && r.width < 320 && r.height > 14 && r.height < 48, top),
    pick('stat', '[class*=stat i], [class*=metric i], [class*=number i], [class*=counter i]',
      (r) => r.width > 60 && r.height > 30 && r.height < 300, top),
  ].filter(Boolean);

  // Product imagery the site itself uses (UI shots, illustrations, videos) — candidates for the film.
  const media = [];
  for (const el of document.querySelectorAll('img, video, picture source')) {
    const r = el.getBoundingClientRect(); const src = el.currentSrc || el.src || el.getAttribute('srcset') || '';
    if (!src || r.width < 280 || r.height < 160) continue;
    media.push({ kind: el.tagName.toLowerCase(), src: src.split(' ')[0], alt: el.alt || '', w: Math.round(r.width), h: Math.round(r.height) });
  }

  const links = Array.from(document.querySelectorAll('a[href]')).map(a => ({ href: a.href, text: (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\s+/g,' ').slice(0, 60) }));

  return { vars, type: Object.values(type).sort((a,b)=>b.size-a.size), spacing: Object.entries(sp).sort((a,b)=>b[1]-a[1]).slice(0, 12),
           radii: radii.slice(0, 8), shadows, borders, gradients, blur, icons: { stroke, fill }, components, media: media.slice(0, 20), links };
}
"""

PAGE_TEXT_JS = r"""
() => {
  const root = document.querySelector('main') || document.body;
  const out = [];
  const seen = new Set();
  for (const el of root.querySelectorAll('h1, h2, h3, h4, p, li, blockquote, figcaption, [class*=stat i], [class*=quote i]')) {
    const r = el.getBoundingClientRect(); if (r.width < 4 || r.height < 4) continue;
    if (el.closest('nav, footer, header')) continue;
    const t = (el.innerText || '').trim().replace(/\s+/g, ' ');
    if (t.length < 3 || t.length > 600 || seen.has(t)) continue;
    seen.add(t);
    const tag = el.tagName;
    out.push(tag[0] === 'H' ? '#'.repeat(+tag[1]) + ' ' + t : (tag === 'LI' ? '- ' + t : t));
  }
  return { title: document.title, text: out.join('\n').slice(0, 7000) };
}
"""

LOGO_SVG_JS = r"""
(sels) => {
  for (const sel of sels) {
    const host = document.querySelector(sel); if (!host) continue;
    const r = host.getBoundingClientRect(); if (r.top > 200 || r.width < 16) continue;
    const svg = host.tagName.toLowerCase() === 'svg' ? host : host.querySelector('svg');
    if (svg) {
      const clone = svg.cloneNode(true);
      const src = [svg, ...svg.querySelectorAll('*')], dst = [clone, ...clone.querySelectorAll('*')];
      src.forEach((n, i) => { const s = getComputedStyle(n);
        for (const p of ['fill', 'stroke', 'stroke-width', 'opacity', 'fill-rule']) { const v = s.getPropertyValue(p); if (v) dst[i].setAttribute(p, v); } });
      const b = svg.getBoundingClientRect();
      if (!clone.getAttribute('viewBox')) clone.setAttribute('viewBox', `0 0 ${b.width} ${b.height}`);
      clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      clone.removeAttribute('class');
      return { kind: 'inline', svg: clone.outerHTML };
    }
    const img = host.tagName.toLowerCase() === 'img' ? host : host.querySelector('img');
    if (img && /\.svg(\?|$)/i.test(img.currentSrc || img.src)) return { kind: 'file', url: img.currentSrc || img.src };
  }
  return null;
}
"""

PRODUCT_SYSTEM = """You are a creative director's researcher. You read a company's website (several pages + a homepage
screenshot) and write the PRODUCT MODEL a motion designer needs to make a launch film that could only be about
this product. Be concrete: use the product's own nouns, screens and numbers. Never invent facts — if the site
doesn't say it, leave it out and ask about it instead.

Return ONLY JSON:
{
  "name": "product name",
  "one_liner": "what it does, <= 14 words, plain language",
  "category": "e.g. B2B caller identification / business messaging",
  "audience": ["who buys", "who uses"],
  "problem": "the pain in one sentence, in the customer's words",
  "core_objects": ["the nouns that live in this product's world, e.g. 'verified business call', 'green badge', 'SMS template'"],
  "core_actions": ["verbs a user does, e.g. 'verify your brand', 'send a message'"],
  "aha": "the single before→after moment the film should build to",
  "differentiators": ["what makes it different, from the site"],
  "proof": ["hard numbers, customer names, awards exactly as stated on the site"],
  "ui_surfaces": [{"name": "screen/interface the product has", "what_it_shows": "elements on it", "seen_on_site": true}],
  "tone": "3-5 adjectives for voice",
  "visual_personality": "how the brand looks, from the screenshot + design data, 1-2 sentences",
  "motion_personality": {"pace": "calm|measured|snappy|frantic", "easing": "soft ease-out|spring|expo|linear-mechanical",
                         "energy": 1-10, "signature_moves": ["2-4 moves that fit THIS product's world"], "why": "one sentence"},
  "story_seeds": ["3 genuinely different film angles grounded in this product's objects and aha"],
  "questions": [{"q": "a question only the founder can answer, that changes the film", "why": "what it decides", "options": ["2-4 likely answers"]}],
  "asset_needs": [{"kind": "logo_svg|font|product_ui|footage|music|voice|other", "message": "what to upload and why"}],
  "confidence": {"what_it_does": 0-1, "audience": 0-1, "aha": 0-1}
}
Rules: at most 5 questions, only about things the site leaves unclear. story_seeds must not be generic
("show the dashboard") — each names specific objects/moments from this product."""


def _rank_links(links: List[dict], base: str, limit: int) -> List[str]:
    host = urlparse(base).netloc
    scored: Dict[str, float] = {}
    for l in links:
        href = l["href"].split("#")[0].rstrip("/")
        u = urlparse(href)
        if u.netloc != host or SKIP.search(href) or href == base.rstrip("/"):
            continue
        path = (u.path + " " + l.get("text", "")).lower()
        score = sum(3 - i * 0.1 for i, h in enumerate(PAGE_HINTS) if h in path)
        score += 1.0 / (1 + path.count("/"))          # shallow pages explain more
        if score > 0:
            scored[href] = max(scored.get(href, 0), score)
    return [u for u, _ in sorted(scored.items(), key=lambda kv: -kv[1])][:limit]


def _summarize_design(d: dict) -> dict:
    """Raw census → the design system a film can follow."""
    type_rows = [t for t in d["type"] if t["chars"] >= 8]
    body = max(type_rows, key=lambda t: t["chars"]) if type_rows else None
    display = [t for t in type_rows if body and t["size"] > body["size"] * 1.25][:5]
    return {
        "type": {
            "display": display,
            "body": body,
            "small": sorted([t for t in type_rows if body and t["size"] < body["size"]], key=lambda t: -t["chars"])[:2],
            "scale_px": sorted({t["size"] for t in type_rows}, reverse=True)[:10],
        },
        "spacing_px": [float(v) for v, _ in d["spacing"][:8]],
        "radii": [r for r, _ in d["radii"][:5]],
        "shadows": [s for s, _ in d["shadows"][:3]],
        "borders": [b for b, _ in d["borders"][:3]],
        "gradients": [g for g, _ in d["gradients"][:3]],
        "glass": [b for b, _ in d["blur"][:2]],
        "icon_style": "outline" if d["icons"]["stroke"] > d["icons"]["fill"] else "solid",
        "css_vars": {k: v for k, v in d["vars"].items() if re.search(r"color|bg|fg|primary|accent|brand|radius|font|shadow|space|gap", k, re.I)},
        "components": d["components"],
    }


def _save_logo_svg(page, out: Path) -> Optional[str]:
    from .brand import LOGO_SELECTORS
    try:
        got = page.evaluate(LOGO_SVG_JS, LOGO_SELECTORS)
    except Exception:
        return None
    if not got:
        return None
    if got["kind"] == "inline":
        out.write_text(got["svg"])
    else:
        try:
            out.write_bytes(page.request.get(got["url"], timeout=10000).body())
        except Exception:
            return None
    return out.name


def _settle(page):
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    from .brand import _dismiss_overlays
    _dismiss_overlays(page)
    page.add_style_tag(content="html,body{scroll-behavior:auto!important}")
    page.evaluate("""async () => { for (let y = 0; y < Math.min(document.body.scrollHeight, 12000); y += 800) {
        window.scrollTo(0, y); await new Promise(r => setTimeout(r, 90)); } window.scrollTo(0, 0); }""")
    page.wait_for_timeout(500)


def crawl(url: str, project: Project, max_pages: int = 8) -> dict:
    from playwright.sync_api import sync_playwright

    project.ensure()
    out = project.assets / "intel"
    (out / "components").mkdir(parents=True, exist_ok=True)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    if not url.startswith("http"):
        url = "https://" + url

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2, color_scheme="light",
                                  user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
        page = ctx.new_page()
        print(f"[intel] {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        _settle(page)

        raw = page.evaluate(DESIGN_JS)
        design = _summarize_design(raw)
        for c in design["components"]:
            try:
                el = page.query_selector(f"[data-intel='{c['id']}']")
                el.scroll_into_view_if_needed(timeout=2000)
                el.screenshot(path=str(out / "components" / f"{c['id']}.png"), timeout=5000)
                c["shot"] = f"intel/components/{c['id']}.png"
            except Exception:
                pass
        page.evaluate("window.scrollTo(0, 0)")
        logo_svg = _save_logo_svg(page, out / "logo.svg")
        page.screenshot(path=str(out / "pages" / "home.png"))
        pages = [{"url": url, "shot": "intel/pages/home.png", **page.evaluate(PAGE_TEXT_JS)}]

        targets = _rank_links(raw["links"], url, max_pages)
        for i, link in enumerate(targets):
            try:
                page.goto(link, wait_until="domcontentloaded", timeout=30000)
                _settle(page)
                shot = f"intel/pages/p{i + 1}.png"
                page.screenshot(path=str(project.assets / shot))
                pages.append({"url": link, "shot": shot, **page.evaluate(PAGE_TEXT_JS)})
                print(f"[intel]   page {i + 1}/{len(targets)} {link}")
            except Exception as e:
                print(f"[intel]   skip {link}: {e.__class__.__name__}")
        browser.close()

    return {"url": url, "design": design, "logo_svg": f"intel/{logo_svg}" if logo_svg else None,
            "media": raw["media"], "pages": pages}


def understand(site: dict, project: Project, model: Optional[str] = None) -> dict:
    from . import llm
    corpus = "\n\n".join(f"=== PAGE {p['url']} — {p['title']}\n{p['text']}" for p in site["pages"])[:40000]
    d = site["design"]
    design_brief = json.dumps({"type": d["type"]["scale_px"], "radii": d["radii"], "icon_style": d["icon_style"],
                               "glass": bool(d["glass"]), "gradients": len(d["gradients"]),
                               "components": [{k: c.get(k) for k in ("id", "bg", "radius", "shadow", "text")} for c in d["components"]]})
    content = [{"type": "text", "text": f"WEBSITE TEXT\n{corpus}\n\nDESIGN DATA\n{design_brief}\n\nHomepage screenshot:"},
               llm.image_part(project.assets / site["pages"][0]["shot"])]
    t0 = time.time()
    product = llm.chat_json([{"role": "system", "content": PRODUCT_SYSTEM}, {"role": "user", "content": content}],
                            model=model or MODEL, temperature=0.3, max_tokens=8000)
    print(f"[intel] product model via {model or MODEL} in {time.time() - t0:.0f}s")
    return product


def _needs(site: dict, product: dict, project: Project) -> List[dict]:
    needs = []
    brand = json.loads(project.brand_path.read_text()) if project.brand_path.exists() else {}
    needs += [n for n in brand.get("needs", [])]
    if not site.get("logo_svg"):
        needs.append({"kind": "logo_svg", "message": "Logo: no vector logo on the site. Upload an SVG so it stays sharp at any size."})
    ui = [s for s in product.get("ui_surfaces", []) if not s.get("seen_on_site")]
    if ui:
        needs.append({"kind": "product_ui", "message": "Product screens: the site doesn't show " +
                      ", ".join(s["name"] for s in ui[:3]) + ". Upload screenshots so the film's UI matches the real product."})
    seen = {(n["kind"], n["message"][:40]) for n in needs}
    for n in product.get("asset_needs", []):
        if (n.get("kind"), n.get("message", "")[:40]) not in seen:
            needs.append(n)
    return needs


def run(project_name: str, url: str, max_pages: int = 8, model: Optional[str] = None) -> dict:
    project = Project(project_name)
    site = crawl(url, project, max_pages)
    product = understand(site, project, model)
    doc = {"url": site["url"], "product": product, "design": site["design"], "logo_svg": site["logo_svg"],
           "media": site["media"], "pages": [{k: p[k] for k in ("url", "title", "shot")} for p in site["pages"]],
           "needs": _needs(site, product, project), "questions": product.get("questions", [])}
    (project.dir / "intel.json").write_text(json.dumps(doc, indent=2))
    (project.dir / "intel_pages.md").write_text("\n\n".join(f"# {p['url']}\n{p['text']}" for p in site["pages"]))
    print(f"[intel] {product.get('name')}: {product.get('one_liner')}")
    print(f"[intel] {len(site['pages'])} pages · {len(site['design']['components'])} components · "
          f"logo svg {'yes' if site['logo_svg'] else 'no'} · {len(doc['questions'])} questions · {len(doc['needs'])} needs")
    return doc


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Website → design system, components, product model, questions")
    ap.add_argument("project")
    ap.add_argument("url")
    ap.add_argument("--pages", type=int, default=8)
    ap.add_argument("--model", default=None)
    a = ap.parse_args()
    run(a.project, a.url, a.pages, a.model)
