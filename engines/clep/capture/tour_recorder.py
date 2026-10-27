from __future__ import annotations

import json
import time
from pathlib import Path

import browser
import private_blur
import screencast
from browser import VIEWPORT


def record_tour(url: str, out_dir: Path, sections: list | None = None,
                per_section: float = 2.4, max_sections: int = 6,
                headless: bool = True,
                chromium_args: list | None = None,
                local_storage: dict | None = None,
                capture_scale: int = screencast.SCALE,
                private: list | None = None) -> dict:
    """Record a controlled scroll walkthrough (portfolio / showcase tour).

    No data-clep needed: opens the page, settles past the loader, then
    eases through each section (scroll_into_view center + hold) while the
    cursor rests out of the way. `sections` is an optional list of
    {heading, anchor} stops (already grounded by director.ground_sections);
    omitted -> evenly spaced sweep of the full page height.

    Returns a trace.json-compatible dict with kind="clep-tour" plus
    `captions`: [{t0, t1, text}] for the polish pass.
    """
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    def now() -> float:
        return round(time.monotonic() - t0, 3)

    with sync_playwright() as p:
        chromium, ctx = browser.launch(p, record=True, chromium_args=chromium_args,
                                local_storage=local_storage, scale=capture_scale)
        private_blur.install(ctx, private)
        page = ctx.new_page()
        t0 = time.monotonic()
        cursor = [{"t": 0.0, "x": 0.88, "y": 0.94}]
        cast = screencast.Screencast(ctx, page, out_dir, now, VIEWPORT, capture_scale)

        page.goto(url, wait_until="networkidle")
        cast.start()
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        browser.hide_cursor(page)
        page.wait_for_timeout(1400)  # past loaders/hero animation
        try:
            page.evaluate("() => window.scrollTo(0, 0)")
        except Exception:
            pass
        page.wait_for_timeout(600)
        establish_end = now()

        try:
            info = page.evaluate("""() => ({
              h: (document.body ? document.body.scrollHeight : 900),
              vh: window.innerHeight || 900,
              title: (document.title || '')
            })""")
        except Exception:
            info = {}
        page_h = max(float(info.get("h") or 900), 1.0)

        # Resolve each stop to the real element it names (anchor, else a
        # heading with that text). Only a stop that found its heading gets a
        # caption — a request word never captions unrelated content.
        vh = VIEWPORT["height"]
        top_words = ("hero", "top", "intro", "header", "landing", "home", "above the fold")
        find_js = """([a, txt]) => {
          const top = el => el.getBoundingClientRect().top + window.scrollY;
          if (a) { try { const el = document.querySelector(a); if (el) return top(el); } catch (e) {} }
          if (!txt) return null;
          const t = txt.toLowerCase().slice(0, 40);
          for (const q of ['h1,h2,h3,h4', 'section,article']) {
            const hit = [...document.querySelectorAll(q)]
              .find(e => e.offsetParent !== null && (e.innerText || '').toLowerCase().includes(t));
            if (hit) return top(hit);
          }
          return null;
        }"""
        stops: list[dict] = []
        if sections:
            for s in sections[:max_sections]:
                s = s if isinstance(s, dict) else {"heading": str(s)}
                head = str(s.get("heading") or "").strip()
                y, caption = None, ""
                if head.lower() in top_words:
                    y = 0.0
                elif not s.get("matched", True):
                    continue                    # not on this page (director said so)
                else:
                    try:
                        y = page.evaluate(find_js, [s.get("anchor") or "", head])
                    except Exception:
                        y = None
                    if y is not None:
                        caption = head
                stops.append({"y": y, "heading": head, "caption": caption[:70]})
            n = len(stops)
            for i, st in enumerate(stops):      # unknown: spread evenly, uncaptioned
                if st["y"] is None:
                    st["y"] = (0.1 + 0.8 * (i + 1) / (n + 1)) * max(page_h - vh, 0)
        else:
            # Even sweep: hero -> mid sections -> footer-adjacent (never the
            # footer itself — holds on content, not whitespace).
            n = 4
            stops = [{"y": (0.02 + 0.90 * (i + 1) / (n + 1)) * max(page_h - vh, 0),
                      "heading": "", "caption": ""} for i in range(n)]
        # page order (no up-and-down), and no two stops a screen apart or less
        stops.sort(key=lambda st: st["y"])
        kept: list[dict] = []
        for st in stops:
            st["y"] = max(float(st["y"]) - vh * 0.12, 0.0)   # heading near the top, content below
            if kept and st["y"] - kept[-1]["y"] < vh * 0.3:
                kept[-1]["caption"] = kept[-1]["caption"] or st["caption"]
                continue
            kept.append(st)
        stops = kept

        events: list[dict] = [{"t": establish_end, "kind": "establish",
                                "x": 0.5, "y": 0.5, "label": "top"}]
        captions: list[dict] = []
        hold = max(per_section, 1.2)
        for i, s in enumerate(stops):
            # Eased glide (no jump cut), then a readable hold.
            t_scroll = now()
            if browser.glide_scroll(page, s["y"]):
                events.append({"t": t_scroll, "t1": now(), "kind": "scroll", "step": i,
                               "x": 0.5, "y": 0.5, "label": "scroll"})
            t_hold0 = now()
            try:
                page.wait_for_timeout(int(hold * 1000))
            except Exception:
                pass
            t_hold1 = now()
            events.append({"t": t_hold0, "kind": "section", "step": i,
                           "x": 0.5, "y": 0.5, "label": (s["caption"] or s["heading"] or f"stop {i + 1}")[:60]})
            if s["caption"]:
                captions.append({"t0": t_hold0, "t1": t_hold1, "text": s["caption"]})

        # Gentle return toward top for a clean closing frame (no whip-pan:
        # eased glide, short hold).
        browser.glide_scroll(page, 0)
        page.wait_for_timeout(700)
        total = now()

        frames = cast.stop()
        ctx.close()
        chromium.close()

    trace = {
        "kind": "clep-tour",
        "name": "tour",
        "title": (info.get("title") or url or "Tour")[:80],
        "url": url,
        "viewport": {"w": VIEWPORT["width"], "h": VIEWPORT["height"]},
        "video": None,
        "frames": str(out_dir / "frames.json"),
        "duration": total,
        "trim_start": max(0.0, round(establish_end - 0.9, 3)),
        "element": {"x": 0.06, "y": 0.06, "w": 0.88, "h": 0.88},
        "cursor": cursor,
        "typing": {"text": "", "t0": 0.0, "t1": 0.0},
        "click": None,
        "clicks": [],
        "focuses": [],
        "events": events,
        "captions": captions,
        "states_seen": [],
        "steps": [{"action": "tour", "target": (s["caption"] or s["heading"])[:40]} for s in stops],
        "button_label": "",
        "query": "",
        "result_at": total,
        "has_input": False,
        "has_button": False,
    }
    tpath = out_dir / "trace.json"
    tpath.write_text(json.dumps(trace, indent=2))
    print(f"[agent] tour -> {len(frames['frames'])} frames ({total:.1f}s, {len(stops)} stops, "
          f"trim {trace['trim_start']}s)")
    print(f"[agent] trace -> {tpath}")
    return trace
