---
name: reels-engine
description: The HTML contract every reel composition must follow — file layout, the R runtime API, timing, media, sound, and the hard rules the checker enforces. Load this before writing any comp.html.
---

# Reel engine — the HTML contract

A reel is ONE self-contained HTML page (`comp.html`, 1080×1920) whose every frame is a pure
function of time. The renderer calls `window.seek(t)` for each frame (30 fps), screenshots it,
and mixes the audio you declared. Nothing plays in real time.

## Skeleton (copy exactly)

```html
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<script src="data.js"></script>      <!-- window.REEL: beats, words, media, duration (written by the engine) -->
<script src="runtime.js"></script>   <!-- window.R: the helpers below -->
<style>
  html, body { margin: 0; width: 1080px; height: 1920px; overflow: hidden; background: #000; }
  /* your look */
</style>
</head>
<body>
  <!-- your layers: <img> for footage, divs/SVG for type and graphics -->
<script>
  // 1. CONFIG: per-reel content keyed by beat id
  // 2. sound cues (top level, once): R.music(...), R.sfx(...), R.clipAudio(...)
  // 3. R.scene(t => { ...set every element's state from t... })
</script>
</body>
</html>
```

## Hard rules (the checker rejects violations)

- Draw only inside `R.scene(t => ...)`. Set every animated property every frame from `t`.
- No `setTimeout`, `setInterval`, `requestAnimationFrame`, `Date`, `performance.now`, `Math.random` (use `R.hash(i)`).
- No CSS `transition`, `animation`, `@keyframes` — motion comes from `t`.
- No `<video>` or `<audio>` tags. Footage is `<img>` driven by `R.show`; sound is declared with cues.
- No internet URLs. Only media keys from data.js, the listed fonts, inline SVG/CSS.
- Declare sound cues at top level, never inside `R.scene`.
- Something must be on screen in every frame; each `seek` should take < 400 ms (avoid huge DOM rebuilds of hundreds of nodes per frame).

## Data you get (`window.REEL`, mirrored on `R`)

| name | what |
|---|---|
| `R.dur` | reel length in seconds |
| `R.beats` | `[{id, t0, t1, w0, w1, text}]` — beat windows; `w0..w1` index into words |
| `R.beat(id)` / `R.beatAt(t)` | look up a beat |
| `R.words` | `[{w, start, end}]` spoken words with real timings (empty if silent) |
| `R.wordAt(t)` | index of the word being spoken at t (-1 before the first) |
| `R.media[key]` | `{kind: 'video'|'image', dur, w, h}` |

## Helpers

| helper | use |
|---|---|
| `R.show(img, key, local, {mode, speed})` | point an `<img>` at footage `key` at `local` seconds into the clip. `mode`: `clamp` (default) / `loop` / `pingpong`. Images ignore `local`. |
| `R.P(t, a, b, ease)` | eased 0→1 progress of t through [a, b] |
| `R.S(t, a, k=16, z=0.5)` | spring 0→1 (overshoots) starting at a — pops, slams, landings |
| `R.kf(t, [[t0, v0], [t1, v1, ease], ...])` | keyframes; values may be arrays |
| `R.E.*` | easings: `outCubic outQuint outExpo outBack inOutCubic inOutSine inExpo lin …` |
| `R.lerp R.clamp R.hash(i, seed)` | math; hash is the deterministic random |
| `R.shake(t, at, amp, decay)` | `[x, y]` decaying shake after a hit |
| `R.chunks({maxWords, maxChars, gap})` | caption phrases `[{i0, i1, start, end, words, text}]` — compute ONCE outside the scene |
| `R.chunkAt(chunks, t)` | the phrase on screen at t |
| `R.clean(word)` | strip trailing punctuation/quotes for display |
| `R.typed(text, t, at, cps)` | typewriter substring |
| `R.$(id) R.css(el, {...}) R.vis(el, bool) R.tf(x, y, s, r) R.esc(s)` | DOM helpers |

## Sound (mixed by the engine after capture)

- `R.music(name, {gain=0.22, from=0, at=0})` — a bed from the library; auto-ducks under voice, fades out at the end.
- `R.sfx(name, at, gain=0.6)` — one hit at `at` seconds. Land them 0.05–0.15 s BEFORE the visual hit for whooshes, ON it for pops/hits.
- `R.clipAudio(key, at, {from, dur, gain})` — a footage clip's own sound (memes, movie lines).
- The voiceover (`voice.wav`) is added automatically when the reel has one. Never re-add the speaker's audio in talking-head reels.

Library — music: `warm_indie`, `warm_drive`, `deep_minimal`, `dark_techno`.
SFX: `whoosh_soft whoosh_fast whoosh_big swish click pop pop_glass tick clock_tick hit impact_big thud riser typing notify success error counter sting`.

## Fonts

Bundled: `Instrument Serif` (regular + italic). System (always available): `Avenir Next` (weights 400–800),
`Helvetica Neue`, `Arial Black`, `Arial Rounded MT Bold`, `Futura`, `Georgia`, `Menlo`.

## Layout facts

- Canvas 1080×1920. Platform UI covers the top ~200 px and bottom ~380 px and the right ~140 px
  (like/comment rail). Keep text and key action inside x 60–940, y 220–1540 (captions may go to ~1760 on
  reels without bottom UI concerns).
- Footage: `<img>` with `width:100%; height:100%; object-fit:cover` fills any box; move it with `transform`.
- Minimum readable type on a phone: 44 px body, 60+ px captions, 110+ px headlines.

## Self-check before you return

1. Lint rules above all hold. 2. Every beat in `R.beats` is handled (look up by id, fall back sensibly).
3. Every media key you use exists. 4. Text never overflows the frame (shrink or wrap deliberately).
5. Sound cue on every visual hit. 6. No frame is empty or frozen for more than ~1.5 s.
