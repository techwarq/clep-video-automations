from __future__ import annotations

import time

import browser
from browser import VIEWPORT

SIGNATURE_JS = """(name) => {
  const root = document.querySelector(`[data-clep="${name}"]`);
  if (!root) return '';
  const states = [...root.querySelectorAll('[data-clep-state]')].map(e => e.getAttribute('data-clep-state')).join(',');
  return root.getAttribute('data-clep-state') + '|' + states + '|' + root.childElementCount + '|' + root.innerText.length;
}"""
STATES_JS = """(name) => {
  const root = document.querySelector(`[data-clep="${name}"]`);
  if (!root) return [];
  const all = [root, ...root.querySelectorAll('[data-clep-state]')];
  return [...new Set(all.map(e => e.getAttribute('data-clep-state')).filter(Boolean))];
}"""
DOCUMENT_SIGNATURE_JS = "() => document.body ? (document.body.innerText.length + '|' + document.body.getElementsByTagName('*').length) : ''"
PANEL_SCROLL_JS = """(el) => new Promise((done) => {
  let p = el.parentElement;
  while (p && !(/(auto|scroll)/.test(getComputedStyle(p).overflowY) && p.scrollHeight > p.clientHeight + 1)) p = p.parentElement;
  if (!p || p === document.scrollingElement || p === document.body) return done(false);
  const er = el.getBoundingClientRect(), pr = p.getBoundingClientRect();
  if (er.top >= pr.top + pr.height * 0.06 && er.bottom <= pr.bottom - pr.height * 0.06) return done(false);
  const from = p.scrollTop;
  const to = Math.max(0, Math.min(p.scrollHeight - p.clientHeight, from + (er.top + er.height / 2) - (pr.top + pr.height * 0.45)));
  const dur = Math.min(1100, Math.max(550, Math.abs(to - from) * 0.9)), t0 = performance.now();
  const ease = (x) => x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const step = (t) => { const k = Math.min(1, (t - t0) / dur); p.scrollTop = from + (to - from) * ease(k); k < 1 ? requestAnimationFrame(step) : done(true); };
  requestAnimationFrame(step);
})"""
POLL_MS = {"state": 200, "url": 250, "appear": 400, "change": 200}


class FeaturePage:
    """The page around one [data-clep] feature: finds targets, waits for states, glides things into view."""

    def __init__(self, page, name: str, clock, events: list):
        self.page, self.name, self.clock, self.events = page, name, clock, events
        self.scope = f'[data-clep="{name}"]'
        self.has_scope = True

    def states(self) -> list:
        try:
            return self.page.evaluate(STATES_JS, self.name) or []
        except Exception:
            return []

    def signature(self) -> str | None:
        try:
            scoped = self.page.evaluate(SIGNATURE_JS, self.name)
        except Exception:
            scoped = ""
        if scoped:
            return "S:" + scoped
        try:
            whole = self.page.evaluate(DOCUMENT_SIGNATURE_JS)
            return ("D:" + whole) if whole else None
        except Exception:
            return None

    def feature_box(self) -> dict:
        box = (browser.node_info(self.page, self.name) or {}).get("box") or {}
        return {"x": max(box.get("x", 0), 0) / VIEWPORT["width"], "y": max(box.get("y", 0), 0) / VIEWPORT["height"],
                "w": box.get("w", 0) / VIEWPORT["width"], "h": box.get("h", 0) / VIEWPORT["height"]}

    @staticmethod
    def center(locator) -> tuple[float, float]:
        bb = locator.bounding_box() or {}
        return bb.get("x", 0) + bb.get("width", 0) / 2, bb.get("y", 0) + bb.get("height", 0) / 2

    def resolve(self, target: str | None):
        page, scope = self.page, self.scope
        prefix = f"{scope} " if self.has_scope else ""
        wanted = (target or "").strip()
        if wanted in ("", "input"):
            return page.locator(f"{prefix}input:visible, {prefix}textarea:visible, {prefix}[contenteditable]:visible"), "input"
        if wanted in ("file", "input-file"):
            return page.locator(f"{prefix}input[type=file]"), "file"
        if wanted == "primary":
            locator = page.locator(f'{prefix}[data-clep-action="primary"]')
            if locator.count() == 0:
                locator = page.locator(f"{prefix}button, {prefix}input[type=submit]")
            try:
                return locator, (locator.first.inner_text() or "").strip()[:24] or "primary"
            except Exception:
                return locator, "primary"
        if wanted.startswith("action:"):
            action = wanted[7:]
            return page.locator(f'{scope} [data-clep-action="{action}"]' if self.has_scope else f'[data-clep-action="{action}"]'), action or wanted
        if wanted.startswith("text:"):
            needle, area = wanted[5:], scope if self.has_scope else "body"
            locator = page.locator(area + " button", has_text=needle)
            return (locator if locator.count() else page.locator(area, has_text=needle)), needle[:24]
        locator = page.locator(f"{scope} {wanted}") if self.has_scope else page.locator(wanted)
        if self.has_scope and locator.count() == 0:
            locator = page.locator(wanted)
        return locator, wanted[:24]

    def _poll(self, kind: str, timeout: float, done) -> tuple[float | None, list]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if done():
                    return self.clock(), self.states()
            except Exception:
                pass
            self.page.wait_for_timeout(POLL_MS[kind])
        return None, self.states()

    def wait_for(self, spec: dict) -> tuple[float | None, list]:
        wanted = str(spec.get("for") or "change")
        timeout = float(spec.get("timeout") or 4.0)
        if wanted.startswith("time:"):
            try:
                self.page.wait_for_timeout(int(float(wanted[5:]) * 1000))
            except Exception:
                pass
            return self.clock(), self.states()
        if wanted.startswith("url:"):
            return self._poll("url", timeout, lambda: wanted[4:] in self.page.url and self._loaded())
        if wanted.startswith("appear:"):
            return self._poll("appear", timeout, lambda: self._appeared(wanted[7:]))
        if wanted.startswith("state:"):
            return self._poll("state", timeout, lambda: wanted[6:] in self.states())
        before = self.signature()
        return self._poll("change", timeout, lambda: self._changed(before))

    def _changed(self, before: str | None) -> bool:
        current = self.signature()
        return bool(current) and current != before

    def _loaded(self) -> bool:
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        return True

    def _appeared(self, selector: str) -> bool:
        locator = self.page.locator(selector)
        if locator.count() == 0:
            return False
        try:
            locator.first.scroll_into_view_if_needed(timeout=1500)
        except Exception:
            pass
        return True

    def _scroll_event(self, started: float) -> None:
        self.events.append({"t": started, "t1": self.clock(), "kind": "scroll", "x": 0.5, "y": 0.5, "label": "scroll"})

    def reveal(self, locator) -> None:
        try:
            bb = locator.bounding_box()
        except Exception:
            bb = None
        height = VIEWPORT["height"]
        if bb and (bb["y"] < height * 0.08 or bb["y"] + bb["height"] > height * 0.92):
            started = self.clock()
            current = self.page.evaluate("() => (document.scrollingElement || document.documentElement).scrollTop")
            if browser.glide_scroll(self.page, current + bb["y"] + bb["height"] / 2 - height * 0.45):
                self._scroll_event(started)
        try:
            started = self.clock()
            if locator.evaluate(PANEL_SCROLL_JS):
                self._scroll_event(started)
        except Exception:
            pass
        try:
            locator.scroll_into_view_if_needed(timeout=2000)
        except Exception:
            pass
