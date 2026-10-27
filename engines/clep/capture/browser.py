from __future__ import annotations

import json
import math
import time

import screencast

VIEWPORT = {"width": 1440, "height": 900}


def launch(p, record: bool, chromium_args: list | None = None,
            local_storage: dict | None = None, storage_origin: str | None = None,
            scale: int = screencast.SCALE):
    args = list(chromium_args or []) + (screencast.launch_args(scale) if record else [])
    browser = p.chromium.launch(args=args)
    kwargs: dict = {"viewport": VIEWPORT, "accept_downloads": True}
    if record:
        kwargs["device_scale_factor"] = scale
    ctx = browser.new_context(**kwargs)
    if local_storage:
        # Pre-authenticate: seed localStorage before any app script runs, so
        # the recording opens straight on the real screen instead of walking
        # through a login form on camera (which also throws off polish's
        # zoom — it anchors on the *first* typed field/clicked button, so a
        # login step at the start always steals the highlight).
        ctx.add_init_script(f"""
        (() => {{
            const kv = {json.dumps(local_storage)};
            for (const k in kv) localStorage.setItem(k, kv[k]);
        }})();
        """)
    return browser, ctx


class NavigationWatch:
    """Lets a click or key press that starts a page load finish it before the next step runs."""

    GRACE_MS = 250
    COMMIT_TIMEOUT_S = 15.0

    def __init__(self, page):
        self.page, self.requested, self.committed = page, False, False

    def __enter__(self):
        self.page.on("request", self._requested)
        self.page.on("framenavigated", self._navigated)
        return self

    def __exit__(self, *_):
        self.page.remove_listener("request", self._requested)
        self.page.remove_listener("framenavigated", self._navigated)

    def _requested(self, request) -> None:
        if request.is_navigation_request() and request.frame == self.page.main_frame:
            self.requested = True

    def _navigated(self, frame) -> None:
        if frame == self.page.main_frame:
            self.committed = True

    def settle(self) -> None:
        self.page.wait_for_timeout(self.GRACE_MS)
        if not self.requested:
            return
        deadline = time.monotonic() + self.COMMIT_TIMEOUT_S
        while not self.committed and time.monotonic() < deadline:
            self.page.wait_for_timeout(50)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=int(self.COMMIT_TIMEOUT_S * 1000))
        except Exception:
            pass


def ease(u: float) -> float:
    return 4 * u * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


# Eased scroll (cubic in-out, rAF-driven) instead of the instant jump of
# scroll_into_view or the browser's own uneven 'smooth' behaviour.
SCROLL_JS = """async ([y, ms]) => {
  const de = document.scrollingElement || document.documentElement;
  const prev = de.style.scrollBehavior; de.style.scrollBehavior = 'auto';
  const s = de.scrollTop, e = Math.max(0, Math.min(y, de.scrollHeight - innerHeight));
  if (Math.abs(e - s) < 2) { de.style.scrollBehavior = prev; return 0; }
  const t0 = performance.now();
  await new Promise(r => { (function f(n) {
    const u = Math.min(1, (n - t0) / ms);
    const k = u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
    de.scrollTop = s + (e - s) * k;
    u < 1 ? requestAnimationFrame(f) : r();
  })(t0); });
  de.style.scrollBehavior = prev; return e - s;
}"""


def glide_scroll(page, y: float) -> float:
    """Scroll the document to y (px) with an eased glide; returns px moved."""
    try:
        cur = float(page.evaluate("() => (document.scrollingElement || document.documentElement).scrollTop"))
        ms = min(max(520 + abs(y - cur) * 0.35, 650), 1300)
        return float(page.evaluate(SCROLL_JS, [y, ms]) or 0)
    except Exception:
        return 0.0


def box_of(loc) -> dict | None:
    """Element box, normalized to the viewport (clipped to it)."""
    try:
        bb = loc.bounding_box()
    except Exception:
        bb = None
    if not bb or bb["width"] <= 0 or bb["height"] <= 0:
        return None
    W, H = VIEWPORT["width"], VIEWPORT["height"]
    x0, y0 = max(bb["x"], 0), max(bb["y"], 0)
    x1, y1 = min(bb["x"] + bb["width"], W), min(bb["y"] + bb["height"], H)
    if x1 <= x0 or y1 <= y0:
        return None
    return {"x": round(x0 / W, 4), "y": round(y0 / H, 4),
            "w": round((x1 - x0) / W, 4), "h": round((y1 - y0) / H, 4)}


class Hand:
    """The real mouse, moved like a person: an eased, slightly curved path,
    every step logged, so the cursor polish draws matches the page's hover
    and press states frame for frame."""

    def __init__(self, page, clock, log: list, start=(0.88, 0.96)):
        self.page, self.clock, self.log = page, clock, log
        self.x, self.y = start[0] * VIEWPORT["width"], start[1] * VIEWPORT["height"]
        self.log.append({"t": clock(), "x": start[0], "y": start[1]})

    def _note(self):
        self.log.append({"t": self.clock(), "x": round(self.x / VIEWPORT["width"], 5),
                         "y": round(self.y / VIEWPORT["height"], 5)})

    def move(self, x: float, y: float, dur: float | None = None):
        x0, y0 = self.x, self.y
        dist = math.hypot(x - x0, y - y0)
        if dist < 1:
            return
        dur = dur or min(max(0.38 + dist / 1900, 0.45), 0.95)
        # control point bowed sideways by ~10% of the distance: a hand, not a ruler
        bow = 0.10 * dist * (1 if (x - x0) * (y - y0) >= 0 else -1)
        cx = (x0 + x) / 2 - (y - y0) / max(dist, 1) * bow
        cy = (y0 + y) / 2 + (x - x0) / max(dist, 1) * bow
        n = max(10, int(dur * 60))
        t_start = time.monotonic()
        self._note()
        for i in range(1, n + 1):
            e = ease(i / n)
            self.x = (1 - e) ** 2 * x0 + 2 * (1 - e) * e * cx + e * e * x
            self.y = (1 - e) ** 2 * y0 + 2 * (1 - e) * e * cy + e * e * y
            self.page.mouse.move(self.x, self.y)
            self._note()
            ahead = t_start + dur * i / n - time.monotonic()
            if ahead > 0.004:
                self.page.wait_for_timeout(int(ahead * 1000))

    def press(self, x: float, y: float) -> float:
        """Hover a beat, then a real press (down, hold, up). Returns the press time."""
        self.move(x, y)
        self.page.wait_for_timeout(140)
        t = self.clock()
        self.page.mouse.down()
        self.page.wait_for_timeout(90)
        self.page.mouse.up()
        return t


def sdk_export(page, name: str | None = None):
    """Pull SDK registry when instrumented; else None."""
    try:
        if name:
            return page.evaluate("(n) => (window.__CLEP__ && window.__CLEP__.export(n)) || null", name)
        return page.evaluate("() => (window.__CLEP__ && window.__CLEP__.exportAll()) || null")
    except Exception:
        return None


def node_info(page, name: str) -> dict:
    """Fallback DOM inspection for one [data-clep] subtree (no SDK needed)."""
    js = """(name) => {
      const root = document.querySelector(`[data-clep="${name}"]`);
      if (!root) return null;
      const r = root.getBoundingClientRect();
      const q = (sel) => {
        const el = root.querySelector(sel);
        if (!el) return null;
        const b = el.getBoundingClientRect();
        const val = (el.value !== undefined && el.value !== null) ? String(el.value) : "";
        return {x: b.x, y: b.y, w: b.width, h: b.height,
                text: (val || el.innerText || el.placeholder || el.name || '').trim().slice(0, 40)};
      };
      const qInput = () => {
        const cands = [...root.querySelectorAll('input, textarea, [contenteditable]')];
        const vis = cands.find(e => {
          const t = (e.getAttribute('type') || 'text').toLowerCase();
          if (t === 'file' || t === 'hidden') return false;
          const b = e.getBoundingClientRect();
          return b.width > 4 && b.height > 4;
        });
        return vis || null;
      };
      const qBtn = (sel) => {
        const el = root.querySelector(sel);
        if (!el) return null;
        const b = el.getBoundingClientRect();
        return {x: b.x, y: b.y, w: b.width, h: b.height,
                text: (el.innerText || '').trim().slice(0, 40)};
      };
      const qWrap = (el) => {
        if (!el) return null;
        const b = el.getBoundingClientRect();
        const val = (el.value !== undefined && el.value !== null) ? String(el.value) : "";
        return {x: b.x, y: b.y, w: b.width, h: b.height,
                text: (val || el.innerText || el.placeholder || el.name || '').trim().slice(0, 40)};
      };
      const path = [];
      let cur = root;
      for (let i = 0; i < 4 && cur && cur !== document.body; i++) {
        path.unshift(cur.tagName.toLowerCase()
          + (cur.getAttribute('data-clep-state') ? '[state=' + cur.getAttribute('data-clep-state') + ']' : ''));
        cur = cur.parentElement;
      }
      return {
        box: {x: r.x, y: r.y, w: r.width, h: r.height},
        input: qWrap(qInput()),
        // a button marked primary wins over any button that merely comes earlier on the page
        button: qBtn('[data-clep-action="primary"]') || qBtn('button, input[type=submit], [type=button]'),
        component: path,
        state: root.getAttribute('data-clep-state'),
      };
    }"""
    return page.evaluate(js, name)


def hide_cursor(page) -> None:
    try:
        page.add_style_tag(content="* { cursor: none !important; }")
    except Exception:
        pass
