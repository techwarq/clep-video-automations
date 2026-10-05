"""A headless Chromium page with a composition loaded and ready to seek."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from pathlib import Path

from reels import config

ARGS = ["--allow-file-access-from-files", "--disable-web-security", "--hide-scrollbars",
        "--force-color-profile=srgb", "--font-render-hinting=none"]


class Page:
    def __init__(self, page, cdp):
        self.page, self.cdp = page, cdp
        self.console: list[str] = []
        page.on("pageerror", lambda e: self.console.append(f"pageerror: {e}"))
        page.on("console", lambda m: self.console.append(f"console.{m.type}: {m.text}")
                if m.type in ("error", "warning") else None)

    def seek(self, t: float) -> None:
        self.page.evaluate(f"window.seek({t:.5f})")

    def jpeg(self, quality: int = 92) -> bytes:
        r = self.cdp.send("Page.captureScreenshot", {"format": "jpeg", "quality": quality,
                                                     "optimizeForSpeed": True})
        return base64.b64decode(r["data"])

    def still(self, t: float, out: Path, quality: int = 90) -> Path:
        self.seek(t)
        out.write_bytes(self.jpeg(quality))
        return out

    def cues(self) -> list[dict]:
        return self.page.evaluate("window.__reel.cues()")

    def errors(self) -> list[str]:
        js = self.page.evaluate("window.__reel ? window.__reel.errors() : ['runtime.js not loaded']")
        out, self.console = self.console + js, []
        return out


@contextmanager
def open_page(html: Path):
    """Yields a Page for html (a comp.html next to its data.js/runtime.js/media)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=ARGS)
        try:
            page = browser.new_page(viewport={"width": config.W, "height": config.H}, device_scale_factor=1)
            p = Page(page, page.context.new_cdp_session(page))
            page.goto(Path(html).resolve().as_uri())
            page.wait_for_function("window.__reel !== undefined", timeout=15000)
            page.evaluate("window.__reel.ready")
            yield p
        finally:
            browser.close()
