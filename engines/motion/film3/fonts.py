"""Fonts for a film: the brand's own files when the site serves them, else Google Fonts localized to disk."""
from __future__ import annotations

import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FALLBACK = {"display": "Inter", "ui": "Inter", "mono": "JetBrains Mono"}


def _get(url: str) -> Optional[bytes]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            return r.read()
    except Exception:
        return None


def google(family: str, out: Path) -> Optional[str]:
    """Download a Google family (all weights, italics when available); returns its @font-face CSS or None."""
    q = urllib.parse.quote_plus(family)
    for axes in (f"{q}:ital,wght@0,100..900;1,100..900", f"{q}:wght@100..900", f"{q}:ital@0;1", q):
        css = _get(f"https://fonts.googleapis.com/css2?family={axes}&display=swap")
        if css:
            css = css.decode()
            break
    else:
        return None
    (out / "wf").mkdir(parents=True, exist_ok=True)
    def repl(m):
        u = m.group(0); name = Path(urllib.parse.urlparse(u).path).name; dest = out / "wf" / name
        if not dest.exists():
            data = _get(u)
            if data:
                dest.write_bytes(data)
        return f"wf/{name}"
    return re.sub(r"https://fonts\.gstatic\.com/[^)\s]+", repl, css)


def build(look: dict, brand_doc: dict, assets: Path, out: Path) -> Tuple[str, List[str], dict]:
    """→ (fonts.css text, font load descriptors for document.fonts.load, {role: family actually available})."""
    out.mkdir(parents=True, exist_ok=True)
    bfonts = (brand_doc.get("brand") or {}).get("fonts") or {}
    want = {"display": look.get("display_font"), "ui": look.get("ui_font"), "mono": look.get("mono_font")}
    css, loads, have, done = [], [], {}, set()
    for role, fam in want.items():
        fam = (fam or "").strip().strip("'\"")
        if not fam:
            continue
        alt = re.search(r"fallback:?\s*([^)]+)\)", fam, re.I)
        alt = alt.group(1).strip().strip("'\"") if alt else None
        fam = re.sub(r"\s*\(.*?\)\s*", "", fam).strip() or fam
        got = fam if fam.lower() in done else None
        for v in bfonts.values():                      # the site's own font file
            bf = (v.get("family") or "")
            if v.get("src") and (fam.lower() in bf.lower() or bf.lower().split(" brand")[0] in fam.lower()):
                src = assets / v["src"]
                if src.exists():
                    dest = out / "wf" / f"brand_{role}{src.suffix}"; dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dest)
                    css.append(f"@font-face{{font-family:'{fam}';src:url('wf/{dest.name}');font-weight:{v.get('weight') or '100 900'};font-style:normal}}")
                    got = fam
                    break
        if not got and fam.lower() not in done:
            g = google(fam, out)
            if g:
                css.append(g); got = fam
        if not got and alt:
            g = google(alt, out)
            if g:
                css.append(g); got = alt
        if not got:                                     # safe fallback
            fb = FALLBACK[role]
            if fb.lower() not in done:
                g = google(fb, out)
                if g:
                    css.append(g)
            got = fb
        done.add(got.lower())
        have[role] = got
        loads += [f"400 24px '{got}'", f"600 24px '{got}'", f"700 24px '{got}'"]
        if role == "display":
            loads.append(f"italic 400 24px '{got}'")
    (out / "fonts.css").write_text("\n".join(css))
    return "\n".join(css), sorted(set(loads)), have
