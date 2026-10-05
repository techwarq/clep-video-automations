// Reel runtime. Every frame is a pure function of time: window.seek(t) -> Promise.
// No CSS transitions/animations, no timers, no Math.random, no <video>/<audio> tags.
// Footage arrives as pre-extracted JPEG frames (REEL.media), audio is declared with
// R.sfx / R.music / R.clipAudio and mixed by the renderer after capture.
(function () {
  const REEL = window.REEL || {};
  const W = REEL.w || 1080, H = REEL.h || 1920, FPS = REEL.fps || 30;

  // ---------- easing + math ----------
  const E = {
    lin: t => t,
    inQuad: t => t * t,
    outQuad: t => 1 - (1 - t) * (1 - t),
    inOutQuad: t => (t < .5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    outCubic: t => 1 - Math.pow(1 - t, 3),
    inCubic: t => t * t * t,
    inOutCubic: t => (t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuint: t => 1 - Math.pow(1 - t, 5),
    outExpo: t => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    inExpo: t => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
    inOutExpo: t => (t <= 0 ? 0 : t >= 1 ? 1 : t < .5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
    inOutSine: t => -(Math.cos(Math.PI * t) - 1) / 2,
    outBack: (t, s = 1.7) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2),
  };
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, p) => a + (b - a) * p;
  // eased progress of t through [a, b]
  const P = (t, a, b, e = E.outCubic) => e(clamp((t - a) / Math.max(1e-6, b - a)));
  // damped spring that settles at 1, driven by seconds since `a` (k stiffness, z damping)
  const S = (t, a, k = 16, z = 0.5) => {
    const x = t - a;
    if (x <= 0) return 0;
    const wd = k * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * k * x) * (Math.cos(wd * x) + (z * k / wd) * Math.sin(wd * x));
  };
  // keyframes [[t, value, ease?], ...]; value may be a number or an array of numbers
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
  // deterministic pseudo-random in [0,1): use instead of Math.random
  const hash = (i, s = 0) => { const x = Math.sin(i * 127.1 + s * 311.7) * 43758.5453; return x - Math.floor(x); };
  // camera shake that decays after a hit at `at`
  const shake = (t, at, amp = 14, decay = 0.12) => {
    if (t < at) return [0, 0];
    const k = Math.exp(-(t - at) / decay) * amp;
    return [k * Math.sin((t - at) * 97), k * Math.cos((t - at) * 83)];
  };

  // ---------- time windows ----------
  const on = (t, a, b) => t >= a && t < b;
  const beats = REEL.beats || [];
  const beat = id => beats.find(b => b.id === id) || null;
  const beatAt = t => beats.find(b => t >= b.t0 && t < b.t1) || beats[beats.length - 1] || null;

  // ---------- words + caption chunks ----------
  const words = REEL.words || [];
  const wordAt = t => { let k = -1; for (let i = 0; i < words.length; i++) { if (words[i].start - 0.04 <= t) k = i; else break; } return k; };
  // Group spoken words into on-screen caption chunks.
  function chunks({ maxWords = 3, maxChars = 16, gap = 0.35, from = 0, to = words.length } = {}) {
    const out = []; let cur = [];
    const flush = () => { if (cur.length) { out.push(cur); cur = []; } };
    for (let i = from; i < to; i++) {
      const w = words[i]; cur.push(i);
      const chars = cur.reduce((n, j) => n + words[j].w.length + 1, 0);
      const next = words[i + 1];
      if (cur.length >= maxWords || chars > maxChars || /[.,!?;:…—]$/.test(w.w) || (next && next.start - w.end > gap)) flush();
    }
    flush();
    return out.map((ix, n) => {
      const nxt = out[n + 1];
      const start = words[ix[0]].start - 0.05;
      const end = nxt && words[nxt[0]].start - words[ix[ix.length - 1]].end < 0.6 ? words[nxt[0]].start - 0.05 : words[ix[ix.length - 1]].end + 0.25;
      return { i0: ix[0], i1: ix[ix.length - 1], start, end, words: ix.map(j => words[j]), text: ix.map(j => words[j].w).join(' ') };
    });
  }
  const chunkAt = (list, t) => list.find(c => t >= c.start && t < c.end) || null;
  const clean = w => w.replace(/[.,;:…—–]+$/, '').replace(/^["“‘']|["”’']$/g, '');

  // ---------- media (pre-extracted frames) ----------
  const media = REEL.media || {};
  const pending = new Set();
  function frame(key, local = 0, { mode = 'clamp', speed = 1 } = {}) {
    const m = media[key];
    if (!m) throw new Error(`unknown media key "${key}" (have: ${Object.keys(media).join(', ')})`);
    if (m.kind === 'image') return m.src;
    let i = Math.floor(Math.max(0, local) * speed * m.fps + 1e-6);
    const n = m.frames;
    if (mode === 'loop') i = i % n;
    else if (mode === 'pingpong') { const p = 2 * (n - 1); i = i % p; if (i >= n) i = p - i; }
    else i = Math.min(n - 1, i);
    return `${m.dir}/${String(i + 1).padStart(5, '0')}.jpg`;
  }
  // Point an <img> at the media frame for local time `local` (seconds into the clip).
  function show(el, key, local = 0, opts) {
    if (typeof el === 'string') el = document.getElementById(el);
    const src = frame(key, local, opts);
    if (el.getAttribute('src') !== src) {
      el.setAttribute('src', src);
      if (!el.complete) pending.add(new Promise(res => { el.onload = el.onerror = () => res(); }));
    }
    return el;
  }

  // ---------- audio cues (declare at top level, never inside render) ----------
  const cues = [];
  const sfx = (name, at, gain = 0.6) => cues.push({ kind: 'sfx', name, at, gain });
  const music = (name, { gain = 0.22, from = 0, at = 0 } = {}) => cues.push({ kind: 'music', name, gain, from, at });
  const clipAudio = (key, at, { from = 0, dur = null, gain = 1 } = {}) => cues.push({ kind: 'clip', key, at, from, dur, gain });

  // ---------- DOM helpers ----------
  const $ = id => document.getElementById(id);
  function css(el, o) { if (typeof el === 'string') el = $(el); for (const k in o) el.style[k] = o[k]; return el; }
  const vis = (el, v) => { if (typeof el === 'string') el = $(el); el.style.display = v ? '' : 'none'; return v; };
  const tf = (x = 0, y = 0, s = 1, r = 0) => `translate(${x.toFixed(2)}px,${y.toFixed(2)}px) scale(${s.toFixed(4)}) rotate(${r.toFixed(2)}deg)`;
  const typed = (s, t, at, cps = 28) => s.slice(0, Math.max(0, Math.floor((t - at) * cps)));
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ---------- scene registry + seek ----------
  const scenes = [];
  const scene = fn => scenes.push(fn);
  let errors = [];
  window.addEventListener('error', e => errors.push(String(e.message)));

  // Engine fonts (library/fonts) — system fonts like Avenir Next / Arial Black / Menlo also work.
  const fontCss = document.createElement('style');
  fontCss.textContent = (REEL.fonts || []).map(f => `@font-face{font-family:'${f.family}';src:url('${f.url}');font-style:${f.style || 'normal'};}`).join('\n');
  document.head.appendChild(fontCss);

  async function seek(t) {
    for (const fn of scenes) fn(t);
    if (pending.size) { const p = [...pending]; pending.clear(); await Promise.all(p); }
    const imgs = [...document.images].filter(i => i.getAttribute('src') && !i.complete);
    if (imgs.length) await Promise.all(imgs.map(i => new Promise(res => { i.onload = i.onerror = () => res(); })));
  }

  window.R = {
    W, H, FPS, dur: REEL.dur || 10, E, clamp, lerp, P, S, kf, hash, shake, on,
    beats, beat, beatAt, words, wordAt, chunks, chunkAt, clean,
    media, frame, show, sfx, music, clipAudio, cues,
    $, css, vis, tf, typed, esc, scene,
  };
  window.seek = seek;
  window.__reel = {
    ready: (async () => {
      await new Promise(r => (document.readyState === 'complete' ? r() : window.addEventListener('load', r)));
      await Promise.all((REEL.fonts || []).map(f => document.fonts.load(`40px '${f.family}'`).catch(() => null)));
      await document.fonts.ready;
      return true;
    })(),
    errors: () => errors.splice(0),
    cues: () => cues,
  };
})();
