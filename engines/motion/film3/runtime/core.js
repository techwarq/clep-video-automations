// v2 film core. Everything is a pure function of time t (seconds): window.seek(t) -> Promise.
// No CSS transitions, no timers, no Math.random.
(function () {
  const W = 1920, H = 1080;

  // ---------- easing ----------
  const E = {
    lin: t => t,
    inQuad: t => t * t,
    outQuad: t => 1 - (1 - t) * (1 - t),
    inOutQuad: t => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    inCubic: t => t * t * t,
    outCubic: t => 1 - Math.pow(1 - t, 3),
    inOutCubic: t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuint: t => 1 - Math.pow(1 - t, 5),
    inQuint: t => t ** 5,
    inOutQuint: t => (t < .5 ? 16 * t ** 5 : 1 - Math.pow(-2 * t + 2, 5) / 2),
    outExpo: t => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    inExpo: t => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
    inOutExpo: t => (t <= 0 ? 0 : t >= 1 ? 1 : t < .5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
    inOutSine: t => -(Math.cos(Math.PI * t) - 1) / 2,
    outBack: (t, s = 1.7) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2),
    // damped spring, settles at 1. k = stiffness-ish, z = damping ratio
    spring: (t, k = 14, z = 0.55) => {
      if (t <= 0) return 0;
      const w = k, wd = w * Math.sqrt(1 - z * z);
      return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
    },
  };
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  // progress of t through [a,b], eased
  const P = (t, a, b, e = E.outCubic) => e(clamp((t - a) / Math.max(1e-6, b - a)));
  // spring progress: seconds since start, not normalized
  const S = (t, a, k = 14, z = 0.55) => (t <= a ? 0 : E.spring(t - a, k, z));

  // keyframes: [[t, v, ease?], ...]  ease applies to the segment ending at that key
  function kf(t, tab, def = E.inOutCubic) {
    if (t <= tab[0][0]) return tab[0][1];
    for (let i = 1; i < tab.length; i++) {
      const [t1, v1, e] = tab[i];
      if (t <= t1) {
        const [t0, v0] = tab[i - 1];
        const p = (e || def)(clamp((t - t0) / Math.max(1e-6, t1 - t0)));
        return Array.isArray(v0) ? v0.map((x, j) => lerp(x, v1[j], p)) : lerp(v0, v1, p);
      }
    }
    return tab[tab.length - 1][1];
  }
  // numerical velocity of a scalar function of t (per second) for motion blur hints
  const vel = (f, t, dt = 1 / 120) => (f(t + dt) - f(t - dt)) / (2 * dt);

  // deterministic hash in [0,1)
  const hash = (i, s = 0) => { const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };

  // beat grid
  function grid(first, beat, perBar = 4) {
    return {
      beat,
      bar: beat * perBar,
      // b(bar, beat=1, sub=0, div=2): sub-divisions of a beat (div=2 -> 8ths, 4 -> 16ths)
      b: (bar, bt = 1, sub = 0, div = 2) => first + (bar - 1) * beat * perBar + (bt - 1) * beat + sub * beat / div,
    };
  }

  // ---------- image + sequence loading (awaited by seek) ----------
  const cache = new Map();
  function img(url) {
    let p = cache.get(url);
    if (!p) {
      p = new Promise((res, rej) => {
        const im = new Image();
        im.onload = () => (im.decode ? im.decode().then(() => res(im), () => res(im)) : res(im));
        im.onerror = () => rej(new Error('load ' + url));
        im.src = url;
      });
      cache.set(url, p);
      if (cache.size > 400) { const k = cache.keys().next().value; cache.delete(k); }
    }
    return p;
  }
  class Seq {
    constructor(dir, count, fps = 60) { this.dir = dir; this.count = count; this.fps = fps; }
    // local seconds -> frame image. mode: clamp | loop | pingpong
    at(local, mode = 'clamp') {
      let i = Math.round(local * this.fps);
      const n = this.count;
      if (mode === 'loop') i = ((i % n) + n) % n;
      else if (mode === 'pingpong') { const m = 2 * (n - 1); i = ((i % m) + m) % m; if (i >= n) i = m - i; }
      else i = Math.max(0, Math.min(n - 1, i));
      return img(`${this.dir}/${String(i + 1).padStart(4, '0')}.jpg`);
    }
  }

  // ---------- canvas helpers ----------
  function rr(ctx, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  // draw image cover-fit into rect, with zoom around focus (fx,fy in 0..1 of the image)
  function cover(ctx, im, x, y, w, h, { zoom = 1, fx = 0.5, fy = 0.5, radius = 0, alpha = 1, filter = '' } = {}) {
    const iw = im.naturalWidth || im.width, ih = im.naturalHeight || im.height;
    const s = Math.max(w / iw, h / ih) * zoom;
    const dw = iw * s, dh = ih * s;
    const dx = x + (w - dw) * fx, dy = y + (h - dh) * fy;
    ctx.save();
    if (radius > 0) { rr(ctx, x, y, w, h, radius); ctx.clip(); } else { ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); }
    ctx.globalAlpha = alpha;
    if (filter) ctx.filter = filter;
    ctx.drawImage(im, dx, dy, dw, dh);
    ctx.restore();
  }

  // halftone: sample `src` (image or canvas) cover-fit into rect, draw round dots of `color`.
  // cell = dot pitch in px. gain/gamma shape the tone curve; minDot hides specks.
  const _ht = document.createElement('canvas');
  const _htx = _ht.getContext('2d', { willReadFrequently: true });
  function halftone(ctx, src, x, y, w, h, o = {}) {
    const { cell = 12, gain = 1.15, gamma = 0.9, color = '#fff', zoom = 1, fx = .5, fy = .5, minDot = 0.06,
      alpha = 1, jitter = 0, offset = 0, lift = 0 } = o;
    const cols = Math.ceil(w / cell) + 1, rows = Math.ceil(h / cell) + 1;
    _ht.width = cols; _ht.height = rows;
    const iw = src.naturalWidth || src.width, ih = src.naturalHeight || src.height;
    const s = Math.max(w / iw, h / ih) * zoom;
    const dw = iw * s / cell, dh = ih * s / cell;
    _htx.imageSmoothingQuality = 'high';
    _htx.fillStyle = '#000'; _htx.fillRect(0, 0, cols, rows);
    _htx.drawImage(src, (cols - dw) * fx, (rows - dh) * fy, dw, dh);
    const d = _htx.getImageData(0, 0, cols, rows).data;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = color;
    ctx.beginPath();
    const rmax = cell * 0.56;
    for (let j = 0; j < rows; j++) {
      const shift = (j % 2) * cell * 0.5 * offset;
      for (let i = 0; i < cols; i++) {
        const k = (j * cols + i) * 4;
        let L = (0.2126 * d[k] + 0.7152 * d[k + 1] + 0.0722 * d[k + 2]) / 255;
        L = clamp(Math.pow(clamp(L * gain + lift), gamma));
        if (L < minDot) continue;
        const r = rmax * Math.sqrt(L);
        const jx = jitter ? (hash(i * 7 + j * 131) - .5) * jitter : 0;
        const px = x + i * cell + shift + jx, py = y + j * cell;
        ctx.moveTo(px + r, py);
        ctx.arc(px, py, r, 0, Math.PI * 2);
      }
    }
    ctx.fill();
    ctx.restore();
    return { cols, rows, data: d };
  }

  // film grain overlay, pre-rendered tiles cycled deterministically by frame
  const grainTiles = [];
  function makeGrain(n = 6, size = 256, strength = 38) {
    for (let g = 0; g < n; g++) {
      const c = document.createElement('canvas'); c.width = c.height = size;
      const x = c.getContext('2d'); const id = x.createImageData(size, size);
      for (let i = 0; i < size * size; i++) {
        const v = 128 + (hash(i, g + 1) - .5) * strength * 2;
        id.data[i * 4] = id.data[i * 4 + 1] = id.data[i * 4 + 2] = v; id.data[i * 4 + 3] = 255;
      }
      x.putImageData(id, 0, 0); grainTiles.push(c);
    }
  }
  function grain(ctx, t, alpha = 0.06, mode = 'overlay') {
    if (!grainTiles.length) makeGrain();
    const tile = grainTiles[Math.floor(t * 24) % grainTiles.length];
    ctx.save(); ctx.globalAlpha = alpha; ctx.globalCompositeOperation = mode;
    const pat = ctx.createPattern(tile, 'repeat'); ctx.fillStyle = pat; ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }

  // ---------- DOM helpers ----------
  const $ = id => document.getElementById(id);
  function css(el, o) { for (const k in o) el.style[k] = o[k]; return el; }
  function show(el, on) { el.style.display = on ? '' : 'none'; return on; }
  const px = v => `${Math.round(v * 100) / 100}px`;
  // mac cursor svg markup (black arrow, white rim)
  const CURSOR_SVG = '<svg width="34" height="46" viewBox="0 0 34 46" style="overflow:visible"><defs><filter id="csh" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="2.5" stdDeviation="2.2" flood-opacity=".35"/></filter></defs><path filter="url(#csh)" d="M3 2 L3 34 L10.8 26.6 L16.2 39.4 L21.4 37.2 L16 24.6 L26.6 24.6 Z" fill="#0b0b0b" stroke="#fff" stroke-width="2.2" stroke-linejoin="round"/></svg>';

  // cursor state from a keyed path: keys [[t, x, y]], clicks [t...]
  function cursorAt(t, keys, clicks = [], ease = E.inOutCubic) {
    const x = kf(t, keys.map(k => [k[0], k[1], k[3] || ease]));
    const y = kf(t, keys.map(k => [k[0], k[2], k[3] || ease]));
    const vx = vel(tt => kf(tt, keys.map(k => [k[0], k[1], k[3] || ease])), t);
    let press = 0;
    for (const c of clicks) { if (t >= c - 0.06 && t <= c + 0.16) press = Math.max(press, Math.sin(clamp((t - (c - 0.06)) / 0.22) * Math.PI)); }
    return { x, y, rot: clamp(vx / 260, -9, 9), scale: 1 - 0.14 * press, press };
  }
  function placeCursor(el, c, visible = true, size = 1) {
    el.style.display = visible ? '' : 'none';
    el.style.transform = `translate(${px(c.x - 3 * size)},${px(c.y - 2 * size)}) rotate(${c.rot.toFixed(2)}deg) scale(${(c.scale * size).toFixed(3)})`;
  }

  async function fontsReady(list) {
    await Promise.all(list.map(f => document.fonts.load(f)));
    await document.fonts.ready;
  }

  window.K = { W, H, E, clamp, lerp, P, S, kf, vel, hash, grid, img, Seq, rr, cover, halftone, grain, $, css, show, px, CURSOR_SVG, cursorAt, placeCursor, fontsReady };
})();
