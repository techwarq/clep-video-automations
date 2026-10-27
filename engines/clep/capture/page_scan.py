from __future__ import annotations

import browser
from browser import VIEWPORT


def discover(url: str, headless: bool = True) -> dict:
    """List every data-clep feature on the page (SDK export preferred)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch(headless=headless)
        page = chromium.new_page(viewport=VIEWPORT)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(800)

        sdk_all = browser.sdk_export(page)
        names: list[str] = []
        if sdk_all:
            names = sorted(sdk_all.keys())
        else:
            try:
                names = page.evaluate(
                    "() => [...new Set([...document.querySelectorAll('[data-clep]')]"
                    ".map(e => e.getAttribute('data-clep')))]")
            except Exception:
                names = []
        vw, vh = VIEWPORT["width"], VIEWPORT["height"]
        features = []
        for name in names:
            sdk = (sdk_all.get(name) or {}) if sdk_all else {}
            info = browser.node_info(page, name) or {}
            box = (info.get("box") or {})
            el = sdk.get("element") or {
                "x": round(max(box.get("x", 0), 0) / vw, 4),
                "y": round(max(box.get("y", 0), 0) / vh, 4),
                "w": round(box.get("w", 0) / vw, 4),
                "h": round(box.get("h", 0) / vh, 4),
            }
            features.append({
                "name": name,
                "title": sdk.get("title") or name.replace("-", " ").title(),
                "url": url, "viewport": {"w": vw, "h": vh},
                "element": el,
                "component": sdk.get("component") or info.get("component") or [],
                "has_input": bool(info.get("input")),
                "has_button": bool(info.get("button")),
                "input_hint": (info.get("input") or {}).get("text", ""),
                "button_label": (info.get("button") or {}).get("text", ""),
                "interactions": sdk.get("interactions") or [],
                "states": sdk.get("states") or [],
            })
        chromium.close()
    return {"url": url, "count": len(features), "features": features}


def scan_content(url: str, headless: bool = True) -> dict:
    """Understand the page: title + headings/sections + data-clep features.

    This is what the director grounds a natural-language request against,
    so "show the portfolio's work section" maps to a real anchor instead
    of a guess. Never requires instrumentation — tours work on any URL.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = p.chromium.launch(headless=headless)
        page = chromium.new_page(viewport=VIEWPORT)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(900)
        try:
            data = page.evaluate("""() => {
              const title = (document.title || '').slice(0, 120);
              const desc = ((document.querySelector('meta[name=description]') || {})
                .content || '').slice(0, 200);
              const h1 = [...document.querySelectorAll('h1')]
                .map(e => e.innerText.trim()).filter(Boolean).slice(0, 3);
              const seen = new Set();
              const sections = [];
              const push = (heading, el) => {
                heading = (heading || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
                if (!heading || seen.has(heading.toLowerCase())) return;
                seen.add(heading.toLowerCase());
                let anchor = null;
                const host = el.closest ? (el.closest('section[id], div[id], article[id]') || el) : el;
                if (host && host.id) anchor = '#' + host.id;
                const r = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
                sections.push({heading, anchor,
                               y: r ? Math.round(r.top + window.scrollY) : 0});
              };
              [...document.querySelectorAll('section, article')]
                .slice(0, 24).forEach(sec => {
                  const h = sec.querySelector('h1, h2, h3');
                  push(h ? h.innerText : (sec.getAttribute('aria-label') || ''), h || sec);
                });
              if (!sections.length) {
                [...document.querySelectorAll('h1, h2')].slice(0, 12)
                  .forEach(h => push(h.innerText, h));
              }
              sections.sort((a, b) => a.y - b.y);
              const names = [...new Set([...document.querySelectorAll('[data-clep]')]
                .map(e => e.getAttribute('data-clep')))].slice(0, 20);
              return {title, desc, h1, sections, names,
                      height: document.body ? document.body.scrollHeight : 0};
            }""")
        except Exception:
            data = {}
        chromium.close()
    data = data or {}
    return {
        "url": url,
        "title": data.get("title", ""),
        "description": data.get("desc", ""),
        "h1": data.get("h1", []),
        "sections": data.get("sections", []),
        "n_sections": len(data.get("sections", [])),
        "features": [{"name": n} for n in (data.get("names") or [])],
        "n_features": len(data.get("names") or []),
        "page_height": data.get("height", 0),
    }
