"""Website → brand kit.

Visits the product's site with Playwright and pulls what the video needs so
it "could only be yours": real colors (computed styles, weighted by where they
appear), real fonts (downloads the @font-face files the site actually serves,
or maps to Google Fonts), the logo (element screenshot, transparent bg), real
screenshots (hero, full page, per-section crops), and the site's own copy.

Writes projects/<name>/brand.json + assets/{shots,brand,fonts}/.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from .paths import Project

VIEWPORT = {"width": 1440, "height": 900}

# Runs in the page: computed-style census of colors + fonts + copy + logo candidates.
PROBE_JS = r"""
() => {
  const parse = (c) => {
    const m = c && c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r,g,b,a=1] = m[1].split(',').map(s=>parseFloat(s));
    if (a < 0.5) return null;
    return '#' + [r,g,b].map(v=>Math.round(v).toString(16).padStart(2,'0')).join('');
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 4 && r.height > 4 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.2;
  };
  // Page background: first opaque bg walking up from body.
  let bg = null;
  for (const el of [document.body, document.documentElement]) { bg = bg || parse(getComputedStyle(el).backgroundColor); }
  const main = document.querySelector('main, #__next, #root, body > div');
  if (!bg && main) bg = parse(getComputedStyle(main).backgroundColor);

  const bgArea = {}, fg = {}, btn = {}, link = {};
  const els = Array.from(document.querySelectorAll('body *')).slice(0, 4000);
  for (const el of els) {
    if (!visible(el)) continue;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const area = Math.min(r.width * r.height, 1440 * 900);
    const b = parse(s.backgroundColor);
    if (b && r.width >= 28 && r.height >= 20) bgArea[b] = (bgArea[b] || 0) + area;
    if (el.childNodes.length && Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 1)) {
      const c = parse(s.color); if (c) fg[c] = (fg[c] || 0) + (el.textContent.trim().length);
    }
    const isBtn = el.matches('button, [role=button], a[class*=btn i], a[class*=button i], input[type=submit]');
    if (isBtn && b) btn[b] = (btn[b] || 0) + 1 + (r.top < 900 ? 2 : 0);
    if (el.tagName === 'A') { const c = parse(s.color); if (c) link[c] = (link[c] || 0) + 1; }
  }
  const fam = (sel) => { const e = document.querySelector(sel); return e ? getComputedStyle(e).fontFamily : null; };
  const txt = (sel, n) => Array.from(document.querySelectorAll(sel)).filter(visible).map(e => e.innerText.trim().replace(/\s+/g,' ')).filter(t => t && t.length < 160).slice(0, n);
  const radius = (() => {
    const b = Array.from(document.querySelectorAll('button, [class*=card i]')).filter(visible).slice(0, 30)
      .map(e => parseFloat(getComputedStyle(e).borderTopLeftRadius)).filter(v => v > 0 && v < 60);
    b.sort((a,b)=>a-b); return b.length ? b[Math.floor(b.length/2)] : null;
  })();
  const meta = (n) => { const e = document.querySelector(`meta[property="${n}"], meta[name="${n}"]`); return e ? e.content : null; };
  const icons = Array.from(document.querySelectorAll('link[rel*=icon]')).map(l => ({ href: l.href, sizes: l.sizes ? l.sizes.value : '' }));
  return {
    bg, bgArea, fg, btn, link, radius,
    fonts: { display: fam('h1') || fam('h2'), body: (() => {
        // Body = the family carrying the most visible text (the first <p> is often a styled tagline).
        const tally = {};
        for (const e of document.querySelectorAll('p, li, td, span, a, button, label')) {
          if (!visible(e)) continue;
          const own = Array.from(e.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
          if (own.length < 2) continue;
          const f = getComputedStyle(e).fontFamily; tally[f] = (tally[f] || 0) + own.length;
        }
        const best = Object.entries(tally).sort((a, b) => b[1] - a[1])[0];
        return best ? best[0] : (fam('p') || fam('body'));
      })(), mono: fam('code, pre, kbd') },
    displayWeight: (() => { const e = document.querySelector('h1') || document.querySelector('h2'); return e ? getComputedStyle(e).fontWeight : null; })(),
    accentItalic: (() => { const e = document.querySelector('h1 em, h1 i, h2 em'); return !!e && getComputedStyle(e).fontStyle === 'italic'; })(),
    // A second face used for emphasis inside headings (Talo: sans headline + Instrument Serif italic words).
    accent: (() => {
      for (const e of document.querySelectorAll('h1 *, h2 *, h3 *')) {
        if (!visible(e) || !e.textContent.trim()) continue;
        const h = e.closest('h1, h2, h3'), s = getComputedStyle(e);
        if (s.fontFamily !== getComputedStyle(h).fontFamily) return { family: s.fontFamily, italic: s.fontStyle === 'italic' };
      }
      return null;
    })(),
    fontCensus: (() => {
      const tally = {};
      for (const e of document.querySelectorAll('body *')) {
        if (!visible(e)) continue;
        const own = Array.from(e.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join('');
        if (own.length < 2) continue;
        const f = getComputedStyle(e).fontFamily; tally[f] = (tally[f] || 0) + own.length;
      }
      return Object.entries(tally).sort((a, b) => b[1] - a[1]).slice(0, 6);
    })(),
    copy: {
      title: document.title, description: meta('description') || meta('og:description'),
      siteName: meta('og:site_name'), ogImage: meta('og:image'),
      h1: txt('h1', 3), h2: txt('h2', 10), h3: txt('h3', 12),
      buttons: txt('button, a[class*=btn i], a[class*=button i], [role=button]', 12),
      nav: txt('nav a, header a', 12), paragraphs: txt('main p, section p', 10),
    },
    icons,
  };
}
"""

LOGO_SELECTORS = [
    # Whole logo link first (mark + wordmark components), then bare marks.
    "a[aria-label*=home i]", "header a[href='/']", "nav a[href='/']", "a[class*=brand i]", "a[class*=logo i]",
    "header a[href='/'] svg", "header a[href='/'] img", "nav a[href='/'] svg", "nav a[href='/'] img",
    "a[aria-label*=home i] svg", "a[aria-label*=home i] img", "[class*=logo i] svg", "[class*=logo i] img",
    "img[alt*=logo i]", "header svg", "header img",
]

GENERIC_FONTS = {"serif", "sans-serif", "monospace", "system-ui", "ui-sans-serif", "ui-monospace", "ui-serif",
                 "-apple-system", "blinkmacsystemfont", "segoe ui", "helvetica", "arial", "roboto", "helvetica neue",
                 "apple color emoji", "segoe ui emoji", "noto color emoji", "menlo", "monaco", "consolas", "courier new"}


# System/OS fonts can't be embedded in a video. Name what the site really uses, then substitute the
# closest free face — and tell the user, so they can upload the real files or pick another font.
SYSTEM_NAMES = {"system-ui": "SF Pro (Apple system font)", "-apple-system": "SF Pro (Apple system font)",
                "blinkmacsystemfont": "SF Pro (Apple system font)", "ui-sans-serif": "SF Pro (Apple system font)",
                "segoe ui": "Segoe UI", "helvetica neue": "Helvetica Neue", "helvetica": "Helvetica", "arial": "Arial",
                "ui-serif": "New York (Apple system serif)", "serif": "the browser's default serif",
                "ui-monospace": "SF Mono (Apple system mono)", "menlo": "Menlo", "monaco": "Monaco", "consolas": "Consolas"}
SUBSTITUTES = {"mono": "JetBrains Mono", "serif": "Newsreader", "sans": "Inter"}


def _system_font(stack: Optional[str]) -> Optional[str]:
    """Human name of the system font a CSS stack resolves to, if it starts with one."""
    first = (stack or "").split(",")[0].strip().strip("'\"").lower()
    return SYSTEM_NAMES.get(first)


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _sat(h: str) -> float:
    r, g, b = [v / 255 for v in _hex_to_rgb(h)]
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def _lum(h: str) -> float:
    r, g, b = [v / 255 for v in _hex_to_rgb(h)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _dist(a: str, b: str) -> float:
    return sum((x - y) ** 2 for x, y in zip(_hex_to_rgb(a), _hex_to_rgb(b))) ** 0.5


def _first_family(stack: Optional[str]) -> Optional[str]:
    if not stack:
        return None
    for f in stack.split(","):
        f = f.strip().strip("'\"")
        clean = _clean_family(f)
        if clean and clean.lower() not in GENERIC_FONTS:
            return clean
    return None


def _clean_family(f: str) -> str:
    # next/font emits "__Inter_a1b2c3" / "__Inter_Fallback_a1b2" — recover "Inter".
    f = re.sub(r"^_+", "", f)
    f = re.sub(r"_Fallback.*$", "", f)
    f = re.sub(r"_[0-9a-f]{5,}$", "", f)
    return f.replace("_", " ").strip()


def _dedupe(text: str) -> str:
    half = len(text) // 2
    if len(text) % 2 == 1 and text[:half] == text[half + 1:]:
        return text[:half]
    return text


def _pick_colors(probe: dict) -> Dict[str, str]:
    bg = probe.get("bg") or (max(probe["bgArea"].items(), key=lambda kv: kv[1])[0] if probe["bgArea"] else "#ffffff")
    fg_counts = Counter(probe.get("fg", {}))
    fg = next((c for c, _ in fg_counts.most_common() if _dist(c, bg) > 140), "#0b0b0c" if _lum(bg) > 0.5 else "#f5f5f4")

    # Primary = most-used saturated button color, else saturated link color, else saturated bg area.
    def saturated(d):
        return [(c, n) for c, n in sorted(d.items(), key=lambda kv: -kv[1]) if _sat(c) > 0.35 and 0.08 < _lum(c) < 0.92
                and _dist(c, bg) > 60]
    btn_sat = saturated(probe.get("btn", {}))
    if btn_sat:
        primary = btn_sat[0][0]
        pool = btn_sat[1:] + saturated(probe.get("link", {})) + saturated(probe.get("bgArea", {}))
    else:
        # Monochrome brand (white CTA on black, black CTA on white): the CTA color IS the brand color;
        # saturated colors found elsewhere (links, illustrations) become the accent.
        btns = sorted(probe.get("btn", {}).items(), key=lambda kv: -kv[1])
        primary = next((c for c, _ in btns if _dist(c, bg) > 80), fg)
        pool = saturated(probe.get("link", {})) + saturated(probe.get("bgArea", {}))
    accent = next((c for c, _ in pool if _dist(c, primary) > 90), None)
    colors = {"background": bg, "foreground": fg, "primary": primary}
    if accent:
        colors["accent"] = accent
    return colors


def _palette(probe: dict, n: int = 8) -> List[str]:
    """Ranked distinct colors (by area + button/link use) — lets the director fix a wrong primary pick."""
    score: Counter = Counter()
    for c, a in probe.get("bgArea", {}).items():
        score[c] += a / 50000
    for c, k in probe.get("btn", {}).items():
        score[c] += k * 40
    for c, k in probe.get("link", {}).items():
        score[c] += k * 3
    out: List[str] = []
    for c, _ in score.most_common():
        if all(_dist(c, o) > 40 for o in out):
            out.append(c)
        if len(out) >= n:
            break
    return out


def _font_faces(page, base_url: str) -> List[dict]:
    """Parse @font-face rules from every stylesheet (fetching cross-origin CSS directly)."""
    css_texts = page.evaluate("""() => {
      const out = [];
      for (const s of document.styleSheets) {
        try { out.push({href: s.href, text: Array.from(s.cssRules).map(r => r.cssText).join('\\n')}); }
        catch (e) { out.push({href: s.href, text: null}); }
      }
      return out;
    }""")
    faces = []
    for sheet in css_texts:
        text, href = sheet.get("text"), sheet.get("href")
        if text is None and href:
            try:
                text = page.request.get(href, timeout=10000).text()
            except Exception:
                text = ""
        for block in re.findall(r"@font-face\s*{([^}]*)}", text or ""):
            fam = re.search(r"font-family:\s*['\"]?([^;'\"]+)", block)
            src = re.findall(r"url\(['\"]?([^)'\"]+)['\"]?\)\s*format\(['\"]?(woff2|woff|truetype|opentype)", block)
            if not src:
                src = [(u, "") for u in re.findall(r"url\(['\"]?([^)'\"]+\.(?:woff2|woff|ttf|otf)[^)'\"]*)['\"]?\)", block)]
            weight = re.search(r"font-weight:\s*([\d\s]+|bold|normal)", block)
            style = re.search(r"font-style:\s*(\w+)", block)
            if fam and src:
                w = (weight.group(1).strip() if weight else "400").replace("normal", "400").replace("bold", "700")
                faces.append({"family": fam.group(1).strip(), "url": urljoin(href or base_url, src[0][0]), "weight": w,
                              "style": style.group(1) if style else "normal"})
    return faces


def _is_google_font(family: str) -> bool:
    """True if @remotion/google-fonts ships this family (one module per font in dist/esm)."""
    esm = Path(__file__).resolve().parent.parent / "engine" / "node_modules" / "@remotion" / "google-fonts" / "dist" / "esm"
    return (esm / (family.replace(" ", "") + ".mjs")).exists()


def _download_font(page, faces: List[dict], family_raw: str, want_weight: int, out_dir: Path, alias: str,
                   italic: bool = False) -> Optional[dict]:
    fam = _clean_family(family_raw).lower()
    want_style = "italic" if italic else "normal"
    matches = [f for f in faces if _clean_family(f["family"]).lower() == fam and f["style"] == want_style]
    if not matches:
        return None

    def wdist(f):
        nums = [int(x) for x in re.findall(r"\d+", f["weight"])] or [400]
        return 0 if len(nums) == 2 and nums[0] <= want_weight <= nums[1] else min(abs(n - want_weight) for n in nums)
    best = sorted(matches, key=lambda f: (wdist(f), 0 if "woff2" in f["url"] else 1))[0]
    ext = (re.search(r"\.(woff2|woff|ttf|otf)", best["url"]) or [None, "woff2"])[1]
    dest = out_dir / f"{alias}.{ext}"
    try:
        body = page.request.get(best["url"], timeout=15000).body()
        dest.write_bytes(body)
    except Exception:
        return None
    out = {"family": f"{_clean_family(family_raw)} Brand {alias.title()}", "src": f"fonts/{dest.name}", "weight": best["weight"]}
    if italic:
        out["italic"] = True
    return out


def _resolve_font(page, faces, stack: Optional[str], role: str, weight: int, fonts_dir: Path, italic: bool = False):
    """One role's CSS font stack → (FontRef or None, a 'needs' message or None).
    Order: the site's own font file → the same family on Google Fonts → a named substitute for system fonts."""
    if not stack:
        return None, None
    fam_raw = next((f.strip().strip("'\"") for f in stack.split(",")
                    if _clean_family(f.strip().strip("'\"")).lower() not in GENERIC_FONTS), None)
    if fam_raw:
        clean = _clean_family(fam_raw)
        got = _download_font(page, faces, fam_raw, weight, fonts_dir, role, italic)
        if got:
            return got, None
        if _is_google_font(clean):
            ref = {"family": clean, "google": True, **({"weight": weight} if role == "display" else {}),
                   **({"italic": True} if italic else {})}
            return ref, None
        return None, {"kind": "font", "role": role, "family": clean,
                      "message": f"{role.title()} font: the site uses {clean}, but its files couldn't be downloaded. "
                                 f"Upload the font file (woff2/ttf/otf) for {clean}, or name a Google Font to use instead."}
    system = _system_font(stack)
    if not system or role == "accent":
        return None, None
    kind = "mono" if role == "mono" else "serif" if "serif" in system.lower() and "sans" not in system.lower() else "sans"
    sub = SUBSTITUTES[kind]
    ref = {"family": sub, "google": True, "substitute": True, **({"weight": weight} if role == "display" else {})}
    return ref, {"kind": "font", "role": role, "family": system,
                 "message": f"{role.title()} font: the site uses {system}, which is an operating-system font and can't "
                            f"be embedded in a video. Using {sub} as the closest free match. Upload your font files "
                            f"or name the font you want."}


def _dismiss_overlays(page):
    for label in ["Accept all", "Accept", "I agree", "Agree", "Got it", "OK", "Allow all", "Close"]:
        try:
            btn = page.get_by_role("button", name=re.compile(f"^{label}$", re.I)).first
            if btn.is_visible(timeout=300):
                btn.click(timeout=800)
                page.wait_for_timeout(300)
        except Exception:
            pass


def extract(url: str, project: Project, max_sections: int = 6) -> dict:
    from playwright.sync_api import sync_playwright

    project.ensure()
    shots = project.assets / "shots"
    brand_dir = project.assets / "brand"
    fonts_dir = project.assets / "fonts"
    if not url.startswith("http"):
        url = "https://" + url

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=2, color_scheme="light")
        page = ctx.new_page()
        print(f"[brand] loading {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            page.wait_for_load_state("networkidle", timeout=12000)
        except Exception:
            pass
        _dismiss_overlays(page)
        page.wait_for_timeout(1200)

        # Smooth-scroll CSS would make scrollTo() animate and screenshots land mid-page.
        page.add_style_tag(content="html,body{scroll-behavior:auto!important}")
        # Trigger lazy content, then return to top.
        page.evaluate("""async () => { for (let y = 0; y < document.body.scrollHeight; y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } window.scrollTo(0, 0); }""")
        page.wait_for_timeout(800)

        probe = page.evaluate(PROBE_JS)
        colors = _pick_colors(probe)

        # Screenshots — the real UI the video will show.
        page.screenshot(path=str(shots / "hero.png"))
        full_h = page.evaluate("document.body.scrollHeight")
        page.screenshot(path=str(shots / "full.png"), full_page=full_h < 9000,
                        clip=None if full_h < 9000 else {"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 9000})
        screenshots = ["shots/hero.png", "shots/full.png"]
        # Sticky/fixed bars (nav, cookie banners) would sit on top of every section crop — hide them.
        page.evaluate("""() => { for (const e of document.querySelectorAll('body *')) {
            const p = getComputedStyle(e).position;
            if (p === 'fixed' || p === 'sticky') e.setAttribute('data-motion-hidden', e.style.visibility || ''), e.style.visibility = 'hidden'; } }""")
        sections = page.query_selector_all("main section, body > section, main > div > section, [class*=section i]")
        n = 0
        for el in sections:
            if n >= max_sections:
                break
            try:
                box = el.bounding_box()
                if not box or box["height"] < 320 or box["width"] < 800 or box["y"] < 200:
                    continue
                el.scroll_into_view_if_needed(timeout=2000)
                page.wait_for_timeout(250)
                p = shots / f"section_{n}.png"
                # Pad above the section so its heading isn't sliced off (sections often start mid-heading).
                top = page.evaluate("e => e.getBoundingClientRect().top + window.scrollY", el)
                pad = 96
                page.screenshot(path=str(p), full_page=True, timeout=8000,
                                clip={"x": 0, "y": max(0, top - pad), "width": VIEWPORT["width"],
                                      "height": min(box["height"] + pad, 2400)})
                screenshots.append(f"shots/{p.name}")
                n += 1
            except Exception:
                continue
        page.evaluate("""() => { window.scrollTo(0, 0);
            for (const e of document.querySelectorAll('[data-motion-hidden]')) { e.style.visibility = e.getAttribute('data-motion-hidden'); e.removeAttribute('data-motion-hidden'); } }""")
        page.wait_for_timeout(300)

        # Logo: screenshot the element itself with a transparent background.
        logo = None
        for sel in LOGO_SELECTORS:
            try:
                el = page.query_selector(sel)
                if not el:
                    continue
                box = el.bounding_box()
                if not box or box["width"] < 16 or box["height"] < 10 or box["y"] > 200:
                    continue
                # Isolate the mark: hide every other element (incl. header overlays / backdrop blurs),
                # keep only the logo subtree visible, transparent page → clean alpha PNG.
                el.evaluate("""e => {
                  const st = document.createElement('style');
                  st.id = '__logo_iso';
                  st.textContent = 'html,body{background:transparent!important} body *{visibility:hidden!important} body *::before,body *::after{visibility:hidden!important}';
                  document.head.appendChild(st);
                  for (const n of [e, ...e.querySelectorAll('*')]) n.style.setProperty('visibility', 'visible', 'important');
                }""")
                el.screenshot(path=str(brand_dir / "logo.png"), omit_background=True)
                logo = "brand/logo.png"
                break
            except Exception:
                continue

        # Fonts: display / body / mono, plus an accent face if headings mix one in.
        faces = _font_faces(page, url)
        fonts, needs = {}, []
        roles = [("display", probe["fonts"].get("display"), 700, False), ("body", probe["fonts"].get("body"), 400, False),
                 ("mono", probe["fonts"].get("mono"), 400, False)]
        if probe.get("accent"):
            roles.append(("accent", probe["accent"]["family"], 400, bool(probe["accent"].get("italic"))))
        for role, stack, weight, italic in roles:
            if role == "display" and probe.get("displayWeight"):
                weight = int(probe["displayWeight"])
            ref, need = _resolve_font(page, faces, stack, role, weight, fonts_dir, italic)
            if ref:
                fonts[role] = ref
            if need:
                needs.append(need)
        browser.close()

    copy = probe["copy"]
    for k in ("h1", "h2", "h3", "buttons", "paragraphs"):
        copy[k] = [_dedupe(x) for x in copy.get(k) or []]
    name = (copy.get("siteName") or re.split(r"\s[|\-–—:·]\s", copy.get("title") or "")[0] or
            urlparse(url).netloc.replace("www.", "").split(".")[0]).strip()
    brand = {
        "name": name,
        "url": url,
        "tagline": (copy.get("h1") or [None])[0] or copy.get("description"),
        "colors": colors,
        "fonts": fonts,
        "screenshots": screenshots,
    }
    if logo:
        light_path, dark_path = _logo_variants(project.assets / logo)
        brand["logo"] = light_path          # for light backgrounds
        brand["logoOnDark"] = dark_path     # for dark backgrounds
    if probe.get("radius"):
        brand["radius"] = round(float(probe["radius"]))
    brand["mode"] = "dark" if _lum(colors["background"]) < 0.35 else "light"
    if probe.get("accentItalic"):
        brand["accentItalic"] = True

    if not logo:
        needs.append({"kind": "logo", "message": "Logo: couldn't find one on the site. Upload your logo (SVG or a transparent PNG)."})
    census = [{"stack": f, "chars": n, "system": _system_font(f)} for f, n in probe.get("fontCensus") or []]
    doc = {"brand": brand, "palette": _palette(probe), "copy": copy, "extracted_from": url,
           "fontsSeen": census, "needs": needs}
    project.brand_path.write_text(json.dumps(doc, indent=2))
    font_desc = ", ".join("%s=%s" % (k, v["family"]) for k, v in fonts.items()) or "default"
    print("[brand] %s: bg %s fg %s primary %s · fonts %s · logo %s · %d screenshots" % (
        name, colors["background"], colors["foreground"], colors["primary"], font_desc, "yes" if logo else "no",
        len(screenshots)))
    for n in needs:
        print(f"[brand] NEEDS: {n['message']}")
    return doc


def _logo_variants(path: Path):
    """Return (logo for light bg, logo for dark bg). A monochrome logo is recolored for the missing side."""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    px = [p for p in im.getdata() if p[3] > 128]
    if not px:
        return "brand/logo.png", "brand/logo.png"
    lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b, _ in px) / len(px) / 255
    sat = sum((max(p[:3]) - min(p[:3])) / 255 for p in px) / len(px)
    if sat > 0.25:  # colorful logo reads on both
        return "brand/logo.png", "brand/logo.png"
    ink = (11, 11, 12) if lum > 0.5 else (250, 250, 250)
    recolored = Image.new("RGBA", im.size)
    recolored.putdata([(ink[0], ink[1], ink[2], a) for *_, a in im.getdata()])
    other = path.with_name("logo_dark.png" if lum > 0.5 else "logo_light.png")
    recolored.save(other)
    rel_other = f"brand/{other.name}"
    return (rel_other, "brand/logo.png") if lum > 0.5 else ("brand/logo.png", rel_other)


def load(project: Project) -> dict:
    if not project.brand_path.exists():
        raise SystemExit(f"No brand.json for '{project.name}'. Run: python motion.py brand {project.name} --url <site>")
    return json.loads(project.brand_path.read_text())
