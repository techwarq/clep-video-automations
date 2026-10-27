from __future__ import annotations

import json
import time
from pathlib import Path

import browser
import clip_plan
import private_blur
import screencast
from browser import VIEWPORT
from feature_page import FeaturePage

DEFAULT_QUERY = "AI browser agents"
UPLOAD_TARGETS = ".dz-card, .dropzone, [role=button]"


SCOPE_WAIT_MS = 10000
SCOPE_WAIT_MS_TOUR = 1500

class Recording:
    """One feature recorded on a live page: drives each step like a person and logs it for the editor."""

    def __init__(self, page, name: str, out_dir: Path, scale: int, context, type_cps: int):
        self.page, self.name, self.out_dir, self.type_cps = page, name, out_dir, type_cps
        self.started = time.monotonic()
        self.cursor: list[dict] = []
        self.events: list[dict] = []
        self.clicks: list[dict] = []
        self.focuses: list[dict] = []
        self.states_seen: list[str] = []
        self.typing = {"text": "", "t0": 0.0, "t1": 0.0}
        self.first = {"click": None, "input_xy": None, "button_xy": None, "button_label": "", "query_text": ""}
        self.hand = browser.Hand(page, self.now, self.cursor)
        self.cast = screencast.Screencast(context, page, out_dir, self.now, VIEWPORT, scale)
        self.target = FeaturePage(page, name, self.now, self.events)

    def now(self) -> float:
        return round(time.monotonic() - self.started, 3)

    def open(self, url: str, steps: list | None) -> None:
        self.page.goto(url, wait_until="networkidle")
        self.cast.start()
        browser.hide_cursor(self.page)
        visits_pages = any(isinstance(s, dict) and str(s.get("action") or "").lower() == "goto" for s in steps or [])
        try:
            self.page.wait_for_selector(self.target.scope, timeout=SCOPE_WAIT_MS_TOUR if visits_pages else SCOPE_WAIT_MS)
        except Exception:
            if not visits_pages:
                raise RuntimeError(f"[agent] no element [data-clep=\"{self.name}\"] at {url}")
            self.target.has_scope = False
        self.page.wait_for_timeout(700)
        self.establish_end = self.now()
        self.sdk = browser.sdk_export(self.page, self.name) or {}
        self.info = browser.node_info(self.page, self.name) or {}
        self.element = self.target.feature_box()
        scope = self.target.scope
        self.has_input = self.page.locator(f'{scope} input:not([type="file"]), {scope} textarea, {scope} [contenteditable]').count() > 0
        self.has_button = self.page.locator(f'{scope} [data-clep-action="primary"], {scope} button, {scope} input[type=submit]').count() > 0
        self._remember_states(self.target.states())

    def default_query(self, query: str | None) -> str:
        sdk_text = next((s["text"] for s in self.sdk.get("steps") or []
                         if isinstance(s, dict) and s.get("type") == "type" and s.get("text")), None)
        return query or sdk_text or (self.info.get("input") or {}).get("text") or DEFAULT_QUERY

    def auto_steps(self, query: str) -> list:
        steps = [{"action": "type", "target": "input", "value": query}] if self.has_input else []
        if self.has_button:
            steps.append({"action": "click", "target": "primary"})
        return steps + [{"action": "wait", "for": "change", "timeout": 4.0}]

    def _remember_states(self, states: list) -> None:
        self.states_seen += [s for s in states if s not in self.states_seen]

    def _event(self, kind: str, index: int, **fields) -> None:
        at = fields.pop("t") if "t" in fields else self.now()
        self.events.append({"t": at, "kind": kind, "step": index,
                            "x": fields.pop("x", 0.5), "y": fields.pop("y", 0.5), **fields})

    def _skip(self, index: int, label: str) -> None:
        self._event("skip", index, label=label)

    def _located(self, step: dict, default: str, index: int, action: str):
        locator, label = self.target.resolve(step.get("target") or default)
        if locator is None or locator.count() == 0:
            self._skip(index, f"{action}:{step.get('target')}?missing")
            return None, label
        return locator, label

    def run(self, steps: list, query: str) -> None:
        handlers = {"goto": self.goto, "type": self.type, "click": self.click, "upload": self.upload,
                    "wait": self.wait, "press": self.press, "scroll": self.scroll_or_hover, "hover": self.scroll_or_hover}
        for index, step in enumerate(steps):
            action = str(step.get("action") or "").lower()
            handler = handlers.get(action)
            if handler is None:
                self._skip(index, f"unknown:{action}")
                continue
            handler(step, index, query) if action == "type" else handler(step, index)
            clip_plan.mark_highlight(step, index, self.events, self.target.resolve, browser.box_of)

    def goto(self, step: dict, index: int) -> None:
        destination = step.get("url") or ""
        self.page.goto(destination, wait_until="domcontentloaded")
        self.page.wait_for_timeout(900)
        self.target.has_scope = self.page.locator(self.target.scope).count() > 0
        if self.target.has_scope:
            try:
                box = self.target.feature_box()
                if box["w"]:
                    self.element.update(box)
            except Exception:
                pass
        self._remember_states(self.target.states())
        self._event("goto", index, label=destination[:60])

    def type(self, step: dict, index: int, query: str) -> None:
        locator, _ = self._located(step, "input", index, "type")
        if locator is None:
            return
        self.target.reveal(locator.first)
        x, y = self.target.center(locator.first)
        box = browser.box_of(locator.first)
        self.hand.press(x, y)
        self.page.wait_for_timeout(220)
        value = step.get("value") or query
        try:
            secret = (locator.first.get_attribute("type") or "").lower() == "password"
        except Exception:
            secret = False
        started = self.now()
        try:
            locator.first.fill("")
        except Exception:
            self.page.keyboard.press("ControlOrMeta+a")
            self.page.keyboard.press("Backspace")
        self.page.keyboard.type(value, delay=int(1000 / max(self.type_cps, 1)))
        ended = self.now()
        if not self.typing["text"]:
            self.typing.update({"text": "" if secret else value, "t0": started, "t1": ended})
            self.first["query_text"] = "" if secret else value
        width, height = VIEWPORT["width"], VIEWPORT["height"]
        self.first["input_xy"] = self.first["input_xy"] or {"x": round(x / width, 4), "y": round(y / height, 4)}
        self.focuses.append({"t": started, "x": x / width, "y": y / height, "label": "type"})
        self._event("type", index, t=ended, t0=started, x=x / width, y=y / height,
                    label="••••••" if secret else value[:40], box=box)

    def click(self, step: dict, index: int) -> None:
        locator, label = self._located(step, "primary", index, "click")
        if locator is None:
            return
        self.target.reveal(locator.first)
        x, y = self.target.center(locator.first)
        box = browser.box_of(locator.first)
        try:
            label = (locator.first.inner_text() or "").strip()[:24] or label
        except Exception:
            pass
        with browser.NavigationWatch(self.page) as navigation:
            pressed = self.hand.press(x, y)
            navigation.settle()
        point = {"t": pressed, "x": x / VIEWPORT["width"], "y": y / VIEWPORT["height"]}
        self.clicks.append(point)
        self.cursor.append({**point, "click": True})
        self.focuses.append({**point, "label": label})
        self._event("click", index, t=pressed, x=point["x"], y=point["y"], label=label, box=box)
        self.first["click"] = self.first["click"] or point
        self.first["button_label"] = self.first["button_label"] or label
        self.first["button_xy"] = self.first["button_xy"] or {"x": round(point["x"], 4), "y": round(point["y"], 4)}

    def upload(self, step: dict, index: int) -> None:
        locator, _ = self.target.resolve(step.get("target") or "file")
        path = Path(step["file"]).resolve() if step.get("file") else None
        if locator is None or locator.count() == 0 or path is None or not path.exists():
            self._skip(index, f"upload:{step.get('target') or step.get('file')}?missing")
            return
        width, height = VIEWPORT["width"], VIEWPORT["height"]
        try:
            proxy = self.page.locator(", ".join(f"{self.target.scope} {s.strip()}" for s in UPLOAD_TARGETS.split(","))).first
            if proxy.count():
                self.target.reveal(proxy)
            x, y = self.target.center(proxy) if proxy.count() else (width / 2, height / 2)
            box = browser.box_of(proxy) if proxy.count() else None
        except Exception:
            x, y, box = width / 2, height / 2, None
        self.hand.move(x, y)
        self.page.wait_for_timeout(300)
        uploaded = self.now()
        locator.first.set_input_files(str(path))
        self.focuses.append({"t": uploaded, "x": x / width, "y": y / height, "label": "upload"})
        self._event("upload", index, t=uploaded, x=x / width, y=y / height, label=path.name[:40], box=box)

    def wait(self, step: dict, index: int) -> None:
        changed_at, states = self.target.wait_for(step)
        self._remember_states(states)
        self.page.wait_for_timeout(1000 if changed_at is not None else 700)
        box = browser.box_of(self.page.locator(self.target.scope).first) if self.target.has_scope else None
        self._event("state", index, t=changed_at if changed_at is not None else self.now(),
                    changed=changed_at is not None and not str(step.get("for") or "").startswith("time:"),
                    label=",".join(states[-2:]) if states else "settled", box=box)

    def press(self, step: dict, index: int) -> None:
        combo = str(step.get("keys") or "")
        if not combo:
            self._skip(index, "press:?keys")
            return
        pressed = self.now()
        with browser.NavigationWatch(self.page) as navigation:
            self.page.keyboard.press(combo)
            navigation.settle()
        self.page.wait_for_timeout(350)
        self._event("press", index, t=pressed, label=clip_plan.keys_label(combo))

    def scroll_or_hover(self, step: dict, index: int) -> None:
        action = str(step.get("action")).lower()
        locator, label = self._located(step, "", index, action)
        if locator is None:
            return
        self.target.reveal(locator.first)
        if action != "hover":
            self.page.wait_for_timeout(500)
            return
        x, y = self.target.center(locator.first)
        self.hand.move(x, y)
        point = {"x": x / VIEWPORT["width"], "y": y / VIEWPORT["height"]}
        self.focuses.append({"t": self.now(), **point, "label": label})
        self._event("hover", index, **point, label=label, box=browser.box_of(locator.first))
        self.page.wait_for_timeout(int(float(step.get("hold") or 0.8) * 1000))

    def finish(self) -> float:
        try:
            self.hand.move(VIEWPORT["width"] * 0.80, VIEWPORT["height"] * 0.72, dur=0.5)
        except Exception:
            pass
        self.page.wait_for_timeout(900)
        total = self.now()
        self.frames = self.cast.stop()
        return total


def build_trace(session: Recording, url: str, steps: list, query: str, total: float, plan_options: dict) -> dict:
    clip_plan.annotate(session.events, steps)
    states = [e for e in session.events if e["kind"] == "state"]
    return {
        "kind": "clep-trace", "name": session.name,
        "title": session.sdk.get("title") or session.name.replace("-", " ").title(),
        "url": url, "viewport": {"w": VIEWPORT["width"], "h": VIEWPORT["height"]}, "video": None,
        "frames": str(session.out_dir / "frames.json"), "duration": total,
        "trim_start": max(0.0, round(session.establish_end - 1.1, 3)),
        "element": {k: round(float(v), 4) for k, v in session.element.items()},
        "input_xy": session.first["input_xy"], "button_xy": session.first["button_xy"],
        "cursor": session.cursor, "typing": session.typing, "click": session.first["click"], "clicks": session.clicks,
        "focuses": session.focuses, "events": session.events, "states_seen": session.states_seen, "steps": steps,
        "button_label": session.first["button_label"], "query": session.first["query_text"] or query,
        "result_at": states[-1]["t"] if states else total, "has_input": session.has_input, "has_button": session.has_button,
        **plan_options,
    }


def record(url: str, name: str, out_dir: Path, query: str | None = None, headless: bool = True, type_cps: int = 14,
           steps: list | None = None, chromium_args: list | None = None, local_storage: dict | None = None,
           capture_scale: int = screencast.SCALE, plan_options: dict | None = None) -> dict:
    """Drive the [data-clep=name] feature on a live page through its steps; save frames + trace.json."""
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)
    plan_options = plan_options or {}
    with sync_playwright() as p:
        chromium, context = browser.launch(p, record=True, chromium_args=chromium_args,
                                           local_storage=local_storage, scale=capture_scale)
        private_blur.install(context, plan_options.get("private"))
        session = Recording(context.new_page(), name, out_dir, capture_scale, context, type_cps)
        try:
            session.open(url, steps)
            typed = session.default_query(query)
            plan_steps = steps or session.auto_steps(typed)
            session.run(plan_steps, typed)
            total = session.finish()
        finally:
            context.close()
            chromium.close()
    trace = build_trace(session, url, plan_steps, typed, total, plan_options)
    path = out_dir / "trace.json"
    path.write_text(json.dumps(trace, indent=2))
    print(f"[agent] captured {len(session.frames['frames'])} frames at {session.frames['scale']}x "
          f"({total:.1f}s, trim {trace['trim_start']}s)")
    print(f"[agent] trace -> {path}")
    return trace
