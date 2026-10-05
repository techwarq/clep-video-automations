---
name: reel-motion-explainer
description: Motion-graphics explainer reels — one continuous take where a single object morphs through every idea, over full-bleed colour, with kinetic type and karaoke captions. Use for "how X works", concepts, numbers, processes, products.
---

# Motion explainer reels

Pure HTML/SVG motion graphics, narrated. Gold example: `examples/motion_explainer.html`.

## The one rule: one take, one carrier
Pick ONE object that can become every idea in the script (a wave, a dot, a card, a bar, a line, a
phone, a coin, a word). Each beat is a new STATE of that object, and the change between states is
animated — it grows, splits, flips, fills, collapses. No slideshow of unrelated scenes, no hard cuts
between beats (colour fields wipe, the carrier transforms).

Carrier ideas: dot → button → card → grid; bar → chart → stack; line → wave → flat line; word → letters
→ particles → word; coin → pile → tower; circle → pie → ring progress.

## Frame design
- Full-bleed colour fields that change per beat (2–5 strong colours from the topic; one light beat for contrast).
- Kicker (mono, tracked caps, `01 — LISTEN`) + a huge headline (110–140 px, tight tracking) top-left,
  words springing in one by one on the beat start.
- The carrier lives in the middle third, BIG (fills 80–90 % of the width). Supporting actors (a chip, a label,
  a number) appear only while their beat needs them.
- Numbers count up (`R.lerp` + `toFixed`), bars grow, lines draw (SVG `stroke-dasharray`).
- Karaoke captions bottom-centre (60–70 px, uppercase), spoken word in the accent colour; adapt
  ink/accent per field so they always read.
- Optional faint grid or grain so flat colour doesn't look empty.

## Motion
- Springs for arrivals (`R.S`), `inOutCubic` for morphs, 0.3–0.6 s per change; nothing static > 1.5 s
  (idle carriers breathe: phase drift, slow rotation, pulse).
- The big change of each beat lands ON its key word (use `R.words[b.w0 + i].start`).

## Sound
- Bed: `deep_minimal` (tech/serious) or `warm_indie` (friendly). `whoosh_soft` into each state,
  `tick` per headline word, `pop_glass`/`hit` on the reveal, `counter` under counting numbers.

## Plan
- `narration: "voice"`, 4–8 beats, usually `assets: []`.
- `look` names the carrier and its states, and the palette. `content` holds per-beat kicker/headline/numbers.
