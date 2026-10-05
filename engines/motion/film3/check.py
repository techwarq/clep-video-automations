"""Headless checks of a compiled film: script errors, layout audit per state, slow frames, HARD-CUT detection,
stills + contact sheet, and solo renders of single states (for the vision check)."""
from __future__ import annotations

import io
import re
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ARGS = ["--disable-web-security", "--allow-file-access-from-files", "--disable-gpu-vsync"]
ARC_GUARD = "{const a=CanvasRenderingContext2D.prototype.arc;CanvasRenderingContext2D.prototype.arc=function(x,y,r,s,e,c){return a.call(this,x,y,Math.max(0,r),s,e,c)}}"


class Page:
    def __init__(self, index: Path, scale: float = 1.0):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        self.b = self.pw.chromium.launch(args=ARGS)
        self.pg = self.b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=scale)
        self.pg.set_default_timeout(120000)
        self.errors: List[str] = []
        self.pg.on("pageerror", lambda e: self.errors.append(str(e)))
        self.pg.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
        self.pg.add_init_script(ARC_GUARD)
        self.pg.goto(Path(index).resolve().as_uri())
        self.pg.evaluate("window.boot()")

    def seek(self, t: float):
        self.pg.evaluate(f"window.seek({t:.5f})")

    def shot(self) -> Image.Image:
        return Image.open(io.BytesIO(self.pg.screenshot(type="jpeg", quality=88))).convert("RGB")

    def close(self):
        self.b.close(); self.pw.stop()


def hold_times(film: dict) -> List[tuple]:
    """(label, t) at the middle of each state's hold."""
    out = []
    occ = film["occ"]
    for i, o in enumerate(occ):
        end = occ[i + 1]["t0"] if i + 1 < len(occ) else film["dur"]
        out.append((f"{o['state']}", round(o["t1"] + 0.55 * max(0.1, end - o["t1"]), 3)))
    return out


def static(index: Path, film: dict) -> dict:
    p = Page(index)
    rep = {"errors": [], "audit": [], "slow": []}
    try:
        for label, t in hold_times(film):
            t0 = time.time(); p.seek(t); ms = (time.time() - t0) * 1000
            if ms > 250:
                rep["slow"].append(f"{label} @ {t:.2f}s takes {ms:.0f} ms per frame")
            for a in p.pg.evaluate("window.audit()"):
                msg = f"{a} (at {t:.2f}s)"
                if not any(msg.split(" (at")[0] == x.split(" (at")[0] for x in rep["audit"]):
                    rep["audit"].append(msg)
        # words: audit at their middle
        for w in film["words"]:
            p.seek((w["t0"] + w["t1"]) / 2)
            for a in p.pg.evaluate("window.audit()"):
                if a.startswith("word") and a not in rep["audit"]:
                    rep["audit"].append(a)
    finally:
        rep["errors"] = sorted(set(p.errors))[:20]
        p.close()
    return rep


def composition(img: Image.Image) -> dict:
    """How much of the frame the film uses. Blocks with structure (edges, or a colour unlike the frame border) are
    content; outlines are closed and filled so a flat white card counts whole. Thresholds adapt to the border's own
    texture, so a dotted or gradient world is not mistaken for content.
    fill = share of the frame that is content · subject = width share of the biggest object · empty = empty cells of 12.
    A frame whose border varies strongly is a full-bleed world; it is not measured (a director judges it by eye)."""
    from scipy import ndimage as nd
    a = np.asarray(img.resize((480, 270)), dtype=np.float32)
    B = 6; bh, bw = 270 // B, 480 // B
    blocks = a[:bh * B, :bw * B].reshape(bh, B, bw, B, 3)
    rng = (blocks.max((1, 3)) - blocks.min((1, 3))).max(-1)
    edge = np.zeros((bh, bw), bool); edge[:2] = edge[-2:] = True; edge[:, :2] = edge[:, -2:] = True
    border = np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3), a[:, :6].reshape(-1, 3), a[:, -6:].reshape(-1, 3)])
    if float(border.std(0).mean()) > 20:                     # full-bleed world (wallpaper, photo, gradient): the world fills it
        return {"fill": 1.0, "subject": 1.0, "empty": 0, "bleed": True}
    dev = np.abs(blocks.mean((1, 3)) - np.median(border, 0)).max(-1)
    m = (rng > max(12, np.percentile(rng[edge], 90) + 8)) | (dev > max(6, np.percentile(dev[edge], 90) + 4))
    m = nd.binary_opening(nd.binary_fill_holes(nd.binary_closing(m, iterations=2)), iterations=1)
    lab, n = nd.label(m); subject = 0.0
    if n:
        i = int(np.argmax(nd.sum(m, lab, range(1, n + 1)))) + 1
        xs = np.where((lab == i).any(0))[0]; subject = (xs.max() - xs.min() + 1) / bw
    empty = sum(m[r * bh // 3:(r + 1) * bh // 3, c * bw // 4:(c + 1) * bw // 4].mean() < 0.03 for r in range(3) for c in range(4))
    return {"fill": round(float(m.mean()), 3), "subject": round(float(subject), 3), "empty": int(empty), "bleed": False}


def scan(index: Path, dur: float, fps: int = 30, every: float = 0.5) -> tuple:
    """One low-res pass over the whole film: frame-to-frame change (for cuts, the drop, frozen holds) and the
    composition every `every` seconds."""
    p = Page(index, scale=0.25)
    try:
        n = int(dur * fps); prev = None; d = []; comp = []; k = max(1, int(round(every * fps)))
        for i in range(n):
            p.seek(i / fps)
            im = p.shot()
            if i % k == 0:
                comp.append({"t": round(i / fps, 2), **composition(im)})
            a = np.asarray(im.resize((240, 135)), dtype=np.float32)
            if prev is not None:
                d.append(float(np.abs(a - prev).mean()))
            prev = a
    finally:
        p.close()
    return np.array(d), comp


def jumps(index: Path, film: dict, fps: int = 30, d: np.ndarray = None) -> List[dict]:
    """Hard-cut detector: a frame that differs from the previous one far more than its neighbours do."""
    if d is None:
        d = scan(index, film["dur"], fps)[0]
    out = []
    for i in range(len(d)):
        before, after = d[max(0, i - 6):max(0, i - 1)], d[i + 2:i + 7]      # a cut spikes against BOTH sides
        base = max(float(np.median(before)) if len(before) else 0, float(np.median(after)) if len(after) else 0)
        if d[i] > 14 and d[i] > 3.5 * base + 4:
            out.append({"t": round((i + 1) / fps, 3), "diff": round(float(d[i]), 1), "around": round(base, 1)})
    return out


def _runs(ts: List[float], gap: float) -> List[tuple]:
    """Consecutive sample times → [(start, end)] runs."""
    out = []
    for t in ts:
        if out and t - out[-1][1] <= gap + 1e-6:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [tuple(r) for r in out]


def craft(d: np.ndarray, comp: List[dict], dur: float, fps: int = 30, drop_t: float = None) -> List[str]:
    """The misses a creative director would point at, measured for free. Thresholds are calibrated so the hand-built
    finals pass (subject ≥ 0.57 of the width, fill ≥ 0.20, ≤ 4 empty cells of 12) and weak drafts fail."""
    out = []
    body = [c for c in comp if 0.6 <= c["t"] <= dur - 4.0]        # skip the fade-in and the end card
    small = _runs([c["t"] for c in body if c["subject"] < 0.50], 0.5)
    empty = _runs([c["t"] for c in body if c["fill"] < 0.12 or c["empty"] >= 6], 0.5)
    for a, b in small:
        if b - a > 0.5:
            out.append(f"main subject small at {a:.1f}–{b:.1f}s (biggest object spans {min(c['subject'] for c in body if a <= c['t'] <= b):.0%} "
                       f"of the width; the references hold 60–80%): scale the carrier or push the camera in")
    for a, b in empty:                                         # brief emptiness around a transition is normal
        if b - a > 1.0:
            w = [c for c in body if a <= c["t"] <= b]
            out.append(f"large empty areas at {a:.1f}–{b:.1f}s (up to {max(c['empty'] for c in w)} of 12 frame cells empty, "
                       f"content fills {min(c['fill'] for c in w):.0%}): bring the subject or its world into the empty space")
    if len(d):
        moving = d > 0.12
        i = 0
        while i < len(d):
            if not moving[i]:
                j = i
                while j < len(d) and not moving[j]:
                    j += 1
                if (j - i) / fps >= 1.2 and i / fps < dur - 3.5:
                    out.append(f"frozen at {i / fps:.1f}–{j / fps:.1f}s (nothing moves): add a slow camera drift, a world drift, or start the next event")
                i = j
            i += 1
        # hold, then move: the hand-built finals' big moves are 4.4–8.5× their typical motion; a film that drifts
        # all the time with weak transitions reads floaty
        body = d[int(0.6 * fps):int(max(0.6, dur - 4.0) * fps)]
        if len(body) > fps * 4:
            med = max(float(np.median(body)), 1e-3); ratio = float(np.percentile(body, 90)) / med
            if ratio < 4.0:
                out.append(f"no contrast between holds and moves (big moves only {ratio:.1f}× the typical motion; the references "
                           f"are 4.4–8.5×): everything drifts a little all the time and no move lands. Let moments settle (drift "
                           f"only the background), then move decisively and fast into the next state")
        # the end card may settle, but not stand still: the hand-built finals hold ≤ 2.7 s (near-still = change < 0.3)
        k = len(d)
        while k > 0 and d[k - 1] < 0.3:
            k -= 1
        if (len(d) - k) / fps > 3.0:
            out.append(f"the ending stands still for {(len(d) - k) / fps:.1f}s ({k / fps:.1f}s → end): keep the end card alive "
                       f"(a slow push, the mark settling, a last detail resolving) or end sooner; ≤ 2.5 s of hold")
        if drop_t is not None and 0 < drop_t < dur:
            med = float(np.median(d)) or 0.01
            w = d[max(0, int((drop_t - 0.1) * fps)):int((drop_t + 0.6) * fps)]
            if len(w) and float(w.max()) < 2.5 * med + 1.0:
                out.append(f"nothing big happens on the drop at {drop_t:.2f}s (peak change {float(w.max()):.1f} vs typical {med:.1f}): "
                           f"the payoff (the carrier's arrival, the reveal) must land ON the drop")
    return out


def label_font(sz=22):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        if Path(f).exists():
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def stills(index: Path, times: List[tuple], out: Path) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True); files = []
    p = Page(index)
    try:
        for label, t in times:
            p.seek(t); f = out / f"{t:07.3f}_{label}.jpg"; p.shot().save(f, quality=88); files.append(f)
    finally:
        p.close()
    return files


def sheet(files: List[Path], labels: List[str], dest: Path, cols: int = 4, w: int = 480) -> Path:
    h = w * 9 // 16; rows = (len(files) + cols - 1) // cols
    im = Image.new("RGB", (cols * w, rows * (h + 30)), (18, 18, 20)); d = ImageDraw.Draw(im); fnt = label_font(18)
    for i, (f, lab) in enumerate(zip(files, labels)):
        x, y = (i % cols) * w, (i // cols) * (h + 30)
        im.paste(Image.open(f).resize((w, h)), (x, y + 30)); d.text((x + 8, y + 5), lab, fill=(230, 230, 230), font=fnt)
    dest.parent.mkdir(parents=True, exist_ok=True); im.save(dest, quality=85)
    return dest


def solo(index: Path, sid: str, lt: float, dest: Path) -> Path:
    p = Page(index)
    try:
        p.pg.evaluate(f"window.solo({sid!r}, {lt:.3f})")
        dest.parent.mkdir(parents=True, exist_ok=True); p.shot().save(dest, quality=90)
        issues = p.pg.evaluate("window.audit()")
    finally:
        p.close()
    return dest, [i for i in issues if i.startswith(f"state {sid}:")]


def report_text(rep: dict, cuts: List[dict]) -> str:
    lines = []
    if rep["errors"]:
        lines.append("SCRIPT ERRORS:\n" + "\n".join(f"- {e}" for e in rep["errors"]))
    if rep["audit"]:
        lines.append("LAYOUT:\n" + "\n".join(f"- {a}" for a in rep["audit"]))
    if rep["slow"]:
        lines.append("SLOW FRAMES:\n" + "\n".join(f"- {s}" for s in rep["slow"]))
    if cuts:
        lines.append("HARD CUTS DETECTED (a frame changes far more than its neighbours — forbidden):\n"
                     + "\n".join(f"- at {c['t']:.2f}s (change {c['diff']} vs {c['around']} around it)" for c in cuts))
    return "\n\n".join(lines) or "no problems found"


# ---------------------------------------------------------------- generic checks (any film page with boot/seek)
AUDIT_JS = r"""() => {
  const W = 1920, H = 1080, out = [];
  const eff = n => { let o = 1; for (let q = n; q && q !== document.body; q = q.parentElement) { const cs = getComputedStyle(q);
    if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
  const texts = [];
  const unq = s => s.replace(/["']/g, '').trim().toLowerCase();
  const loaded = new Set([...document.fonts].filter(f => f.status === 'loaded').map(f => unq(f.family)));
  const generic = /^(sans-serif|monospace|system-ui|ui-[a-z-]+|-apple-system|blinkmacsystemfont|inherit|initial)$/;
  const badFont = new Set();
  const opaque = q => { const cs = getComputedStyle(q), m = cs.backgroundColor.match(/rgba?\(([^)]+)\)/);
    const al = m ? (m[1].split(',')[3] === undefined ? 1 : +m[1].split(',')[3]) : 0;
    return al > 0.5 || cs.backgroundImage !== 'none' || /^(IMG|CANVAS|VIDEO)$/.test(q.tagName); };
  document.querySelectorAll('body *').forEach(n => {
    if (n instanceof SVGElement) return;
    if (!n.childNodes.length || !([...n.childNodes].some(c => c.nodeType === 3 && c.textContent.trim()))) return;
    const box = n.getBoundingClientRect(); if (box.width < 2 || box.height < 2) return;
    const rg = document.createRange(); rg.selectNodeContents(n); const r = rg.getBoundingClientRect();   // the glyphs, not the box
    if (r.width < 2 || r.height < 2) return;
    if (r.right < 0 || r.left > W || r.bottom < 0 || r.top > H) return;
    const o = eff(n); if (o < 0.6) return;
    const k = box.height / (n.offsetHeight || box.height), fs = parseFloat(getComputedStyle(n).fontSize) * k;
    const label = (n.id ? '#' + n.id + ' ' : '') + '"' + n.textContent.trim().slice(0, 28) + '"';
    texts.push({ n, r, label });
    if (fs < 15) out.push(`tiny text ${label} (${fs.toFixed(0)}px on screen)`);
    if (fs >= 30 && (r.left < -4 || r.right > W + 4 || r.top < -4 || r.bottom > H + 4)) out.push(`headline runs off the frame ${label}`);
    const fam = unq(getComputedStyle(n).fontFamily.split(',')[0]);
    if (!generic.test(fam) && !loaded.has(fam)) badFont.add(fam);
    if (fs >= 44 && r.width > 120) {                       // a headline: is it printed over the product UI?
      const anc = new Set(); for (let q = n; q; q = q.parentElement) anc.add(q);
      let hits = 0;
      for (const fx of [0.2, 0.5, 0.8]) {
        const x = r.left + r.width * fx, y = r.top + r.height / 2; if (x < 0 || x >= W || y < 0 || y >= H) continue;
        const under = document.elementsFromPoint(x, y).find(q => !anc.has(q) && !n.contains(q) && q !== document.body && q !== document.documentElement);
        if (!under) continue;
        for (let q = under; q && q !== document.body; q = q.parentElement) {
          const rr = q.getBoundingClientRect(); if (rr.width * rr.height > 0.85 * W * H) break;     // full-bleed world: fine
          if (opaque(q) && eff(q) > 0.5) { hits++; break; }
        }
      }
      if (hits >= 2) out.push(`words over UI ${label}: the headline sits on top of a card/screen; give words their own clear space`);
    }
  });
  document.querySelectorAll('body *').forEach(n => {     // blank stand-ins: a filled box with no content at all
    if (n instanceof SVGElement || /^(IMG|CANVAS|VIDEO)$/.test(n.tagName)) return;
    const r = n.getBoundingClientRect(), area = r.width * r.height / (W * H);
    if (area < 0.015 || area > 0.6 || r.right < 0 || r.left > W || r.bottom < 0 || r.top > H) return;
    const cs = getComputedStyle(n);
    if (!opaque(n) || /url\(/.test(cs.backgroundImage) || /blur/.test(cs.filter) || eff(n) < 0.6) return;
    if (n.textContent.trim() || n.querySelector('img,svg,canvas,video')) return;
    out.push(`blank shape ${n.id ? '#' + n.id : n.className ? '.' + String(n.className).split(' ')[0] : n.tagName.toLowerCase()} (${Math.round(r.width)}×${Math.round(r.height)}px, nothing inside): `
      + `if it stands for something (a photo, a clip, a document, a card), draw the real thing; if it is decoration, blur it or drop it`);
  });
  badFont.forEach(f => out.push(`text set in "${f}", which is not loaded, so the viewer sees a fallback font: call set_fonts with it or use a loaded family`));
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i], b = texts[j]; if (a.n.contains(b.n) || b.n.contains(a.n)) continue;
    const ix = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left), iy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (!(ix > 4 && iy > 4 && ix * iy > 0.2 * Math.min(a.r.width * a.r.height, b.r.width * b.r.height))) continue;
    // occlusion: if an opaque layer of one covers the other at the overlap, the viewer sees only one of them
    const cx = (Math.max(a.r.left, b.r.left) + Math.min(a.r.right, b.r.right)) / 2, cy = (Math.max(a.r.top, b.r.top) + Math.min(a.r.bottom, b.r.bottom)) / 2;
    const top = document.elementFromPoint(Math.max(0, Math.min(W - 1, cx)), Math.max(0, Math.min(H - 1, cy)));
    const upper = top && (a.n.contains(top) || top.contains(a.n) || a.n === top) ? a : top && (b.n.contains(top) || top.contains(b.n) || b.n === top) ? b : null;
    const lower = upper === a ? b : upper === b ? a : null;
    let hidden = false;
    if (upper && lower) { for (let q = upper.n; q && !q.contains(lower.n); q = q.parentElement) {
      const bg = getComputedStyle(q).backgroundColor, m = bg.match(/rgba?\(([^)]+)\)/), al = m ? (m[1].split(',')[3] === undefined ? 1 : +m[1].split(',')[3]) : 0;
      if (al > 0.85 || getComputedStyle(q).backgroundImage !== 'none') { hidden = true; break; } } }
    if (!hidden) out.push(`text overlaps text ${a.label} × ${b.label}`);
  }
  return out.slice(0, 16);
}"""


MOTION_JS = r"""() => {
  const W = 1920, H = 1080, fades = [];
  const eff = n => { let o = 1; for (let q = n; q && q !== document.body; q = q.parentElement) { const cs = getComputedStyle(q);
    if (cs.display === 'none' || cs.visibility === 'hidden') return 0; o *= +cs.opacity; } return o; };
  const opaque = q => { const cs = getComputedStyle(q), m = cs.backgroundColor.match(/rgba?\(([^)]+)\)/);
    const al = m ? (m[1].split(',')[3] === undefined ? 1 : +m[1].split(',')[3]) : 0;
    return al > 0.5 || cs.backgroundImage !== 'none' || /^(IMG|CANVAS|VIDEO)$/.test(q.tagName); };
  const name = n => n.id ? '#' + n.id : n.className && typeof n.className === 'string' ? '.' + n.className.split(' ')[0] : n.tagName.toLowerCase();
  const layers = [];
  document.querySelectorAll('body *').forEach((n, i) => {
    if (n instanceof SVGElement) return;
    const r = n.getBoundingClientRect(), area = r.width * r.height / (W * H);
    if (area < 0.08 || area > 0.85 || r.right < 0 || r.left > W || r.bottom < 0 || r.top > H) return;
    const o = eff(n); if (o < 0.15 || !opaque(n)) return;
    if (layers.some(l => l.n.contains(n))) return;            // the outermost panel only
    layers.push({ n, r, o, area });
  });
  for (let i = 0; i < layers.length; i++) for (let j = i + 1; j < layers.length; j++) {
    const a = layers[i], b = layers[j]; if (a.o > 0.85 && b.o > 0.85) continue;
    if (Math.min(a.o, b.o) > 0.85 || Math.max(a.o, b.o) < 0.15) continue;
    const mid = a.o <= 0.85 ? a : b; if (mid.o < 0.15 || mid.o > 0.85) continue;
    const ix = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left), iy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
    if (ix > 0 && iy > 0 && ix * iy > 0.3 * Math.min(a.r.width * a.r.height, b.r.width * b.r.height))
      fades.push(`${name(a.n)} (${a.o.toFixed(2)}) × ${name(b.n)} (${b.o.toFixed(2)})`);
  }
  return { fades };
}"""


def motion_probe(p: "Page", dur: float, step: float = 0.25) -> List[str]:
    """Whole screens cross-fading through each other for ≥ 0.5 s: a double exposure instead of one object changing.
    (The hand-built finals touch this for one sample at most.)"""
    fades, t = {}, 0.0
    while t < dur:
        p.seek(t); r = p.pg.evaluate(MOTION_JS)
        for f in r["fades"]:
            fades.setdefault(re.sub(r"\(\d\.\d+\)", "", f), []).append(round(t, 2))
        t += step
    out = []
    for f, ts in fades.items():
        if len(ts) < 2:
            continue
        out.append(f"two screens cross-fade through each other ({f.strip()}) at {ts[0]:.2f}–{ts[-1]:.2f}s: a double exposure reads "
                   f"muddy. Keep ONE solid object and change it (reshape the container, reveal the new contents inside it), "
                   f"or move the old one away before the new one arrives")
    return out[:8]


def source_lint(html: str) -> List[str]:
    """Motion habits read straight from the film's code. The hand-built finals all use core.js eases (E.outExpo for
    moves, E.outBack for arrivals) and never sway the UI with a sine. (Move length is NOT checked: maritime's median
    move is 0.83 s, so length alone does not separate good from bad.)"""
    out = []
    if re.search(r"(function\s+P\s*\(|(const|let|var)\s+P\s*=)", html):
        out.append("the film defines its own easing P(): use core.js instead (K.P with E.outExpo for moves, E.outBack or "
                   "S() springs for arrivals) so moves snap and land with a little bounce")
    wob = [l.strip()[:70] for l in html.splitlines()
           if re.search(r"Math\.(sin|cos)\(\s*t\b", l) and re.search(r"translate|scale|margin|top|left|transform|drift", l, re.I)]
    if wob:
        out.append(f"sine wobble moves the picture ({wob[0]}…): constant sub-pixel sway makes text and UI shiver. Hold UI "
                   f"still; let only the background world drift, or push the camera with one slow eased move")
    return out


def film_check(index: Path, dur: float, step: float = 0.5, jumps_fps: int = 30, drop_t: float = None) -> str:
    """Everything a free-form film must pass. Returns a plain report ('CLEAN' when nothing is wrong)."""
    p = Page(index)
    probs, seen, slow = [], {}, []
    try:
        t = 0.0
        while t < dur:
            t0 = time.time(); p.seek(t); ms = (time.time() - t0) * 1000
            if ms > 200:
                slow.append(f"{t:.1f}s: {ms:.0f} ms/frame")
            for a in p.pg.evaluate(AUDIT_JS):
                key = re.sub(r"\d", "#", a)                        # "3 unread" and "4 unread" are one problem
                seen.setdefault(key, [a, []])[1].append(round(t, 2))
            t += step
        moves = motion_probe(p, dur)
        errs = sorted(set(p.errors))[:10]
    finally:
        p.close()
    tiny = []
    for a, ts in seen.values():
        if a.startswith("tiny text"):
            tiny.append((a, ts)); continue
        probs.append(f"- {a} at {ts[0]:.2f}s" + (f"–{ts[-1]:.2f}s" if len(ts) > 1 else ""))
    if tiny:                                                   # one line: fine for a background crowd, not for the subject
        sz = [int(x) for a, _ in tiny for x in re.findall(r"\((\d+)px", a)]
        t0, t1 = min(ts[0] for _, ts in tiny), max(ts[-1] for _, ts in tiny)
        eg = ", ".join(re.search(r'"[^"]*"', a).group(0) for a, _ in tiny[:4])
        probs.append(f"- tiny text ({min(sz)}–{max(sz)}px on screen) in {len(tiny)} elements between {t0:.1f}s and {t1:.1f}s, e.g. {eg}: "
                     f"fine for a background crowd, not for the main subject or its action")
    d, comp = scan(index, dur, fps=jumps_fps)
    cuts = jumps(index, {"dur": dur}, fps=jumps_fps, d=d)
    look = craft(d, comp, dur, fps=jumps_fps, drop_t=drop_t)
    parts = []
    if errs:
        parts.append("SCRIPT ERRORS:\n" + "\n".join(f"- {e}" for e in errs))
    if cuts:
        parts.append("HARD CUTS (a frame changes far more than its neighbours):\n" + "\n".join(f"- at {c['t']:.2f}s (change {c['diff']} vs {c['around']})" for c in cuts))
    if probs:
        parts.append("LAYOUT:\n" + "\n".join(probs[:25]))
    if look or moves:
        parts.append("CRAFT (measured from the frames):\n" + "\n".join(f"- {s}" for s in (look + moves)[:12]))
    lint = source_lint(Path(index).read_text())
    if lint:
        parts.append("MOTION (read from the code):\n" + "\n".join(f"- {s}" for s in lint))
    if slow:
        parts.append("SLOW FRAMES (keep seek under 200 ms):\n" + "\n".join(f"- {s}" for s in slow[:5]))
    return "\n\n".join(parts) or "CLEAN"
