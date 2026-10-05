"""Understand the product: site intel (multi-page crawl, design system, product model) + brand kit + marks."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.parse import urlparse

from director import app_logos, brand, site_intel
from director.paths import Project


def build(name: str, url: str, refresh: bool = False) -> dict:
    pr = Project(name).ensure()
    if refresh or not pr.brand_path.exists():
        brand.extract(url, pr)
    if refresh or not (pr.dir / "intel.json").exists():
        import time
        from film3 import llm as L
        for attempt, model in enumerate((None, None, L.MODEL)):     # cheap default, again after a pause, then the director model
            try:
                site_intel.run(name, url, model=model)
                break
            except L.BudgetExceeded:
                raise
            except RuntimeError as e:
                if attempt == 2:
                    raise
                print(f"[film3] product model failed ({str(e)[:90]}…) — retrying{' with ' + L.MODEL if attempt == 1 else ' in 30s'}")
                if attempt == 0:
                    time.sleep(30)
    intel = json.loads((pr.dir / "intel.json").read_text())
    bdoc = json.loads(pr.brand_path.read_text())
    a = pr.assets

    marks = {}
    if intel.get("logo_svg") and (a / "intel" / intel["logo_svg"]).exists():
        marks["logo_svg"] = a / "intel" / intel["logo_svg"]
    for k, rel in (("logo_png", bdoc["brand"].get("logo")), ("logo_on_dark", bdoc["brand"].get("logoOnDark"))):
        if rel and (a / rel).exists():
            marks[k] = a / rel
    icon = a / "brand" / "site_icon.png"
    if not icon.exists():
        try:
            got = app_logos._site_icon(urlparse(url).netloc)
            if got:
                shutil.copyfile(got, icon)
        except Exception:
            pass
    if icon.exists():
        marks["icon"] = icon

    pages_md = (pr.dir / "intel_pages.md").read_text() if (pr.dir / "intel_pages.md").exists() else ""
    shots = [a / p["shot"] for p in intel.get("pages", []) if p.get("shot") and (a / p["shot"]).exists()]
    comps = [a / c["shot"] for c in intel["design"].get("components", []) if c.get("shot") and (a / c["shot"]).exists()]
    return {"name": name, "url": url, "project": pr, "intel": intel, "brand": bdoc, "marks": marks,
            "pages_md": pages_md, "shots": shots, "component_shots": comps}


def design_digest(ctx: dict) -> dict:
    """The design data the director needs, compact."""
    d = ctx["intel"]["design"]; b = ctx["brand"]["brand"]
    return {
        "colors": b.get("colors"), "palette": ctx["brand"].get("palette"), "mode": b.get("mode"),
        "fonts": {k: v.get("family") for k, v in (b.get("fonts") or {}).items()},
        "type": {"display": d["type"].get("display", [])[:4], "body": d["type"].get("body"), "scale_px": d["type"].get("scale_px")},
        "radii": d.get("radii"), "shadows": d.get("shadows"), "borders": d.get("borders"), "gradients": d.get("gradients", [])[:3],
        "glass": d.get("glass"), "icon_style": d.get("icon_style"),
        "css_vars": dict(list((d.get("css_vars") or {}).items())[:40]) if isinstance(d.get("css_vars"), dict) else d.get("css_vars"),
        "components": [{k: c.get(k) for k in ("id", "bg", "color", "radius", "padding", "border", "shadow", "font", "backdrop", "text")}
                       for c in d.get("components", [])],
        "look_observed": ctx["brand"].get("look", {}).get("observations"),
    }
