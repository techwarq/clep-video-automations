---
name: reel-talking-head
description: Edited talking-head reels — the speaker's own video with punch-in zooms, Pinterest B-roll cut-ins, slam callouts, bold karaoke captions and a progress bar. Use when the user supplies a video of someone talking.
---

# Talking-head reels

The speaker's video is the spine (media key `face`, its sound is already the voiceover). The edit's job
is to keep eyes on screen while they talk. Gold example: `examples/talking_head.html`.

## Edit toolkit
- **Punch-ins**: alternate zoom per sentence (1.0 ↔ 1.15–1.25, origin on the face ~38 % from top) with a tiny
  snap on the change. This hides jump cuts and resets attention every sentence.
- **B-roll cut-ins** (Pinterest): `full` replaces the face while the voice continues (for "imagine…",
  examples, places, objects); `card` floats a rounded clip over the top half (for "look at this", proof,
  products). 1 B-roll every 2–3 beats; never over the hook sentence.
- **Callouts**: the key number/phrase slams in on its word (white pill, black 120–150 px type, slight
  rotation, `pop`). Max one per beat.
- **Captions**: 1–3 words, 80–90 px Avenir 800 uppercase with a thick black stroke, active word on an
  accent box. Centre-lower (y≈1330) so they sit under the chin, above the platform UI.
- **Progress bar**: thin accent line at the very top growing with time (retention).

## Rules
- The face must always be running in real time: `R.show('face', 'face', t)` — never loop or speed it.
- Never add the face's audio again; music bed low (0.10–0.14) under the voice.
- Keep faces out from behind text: callouts go in the upper third or over B-roll, not over the mouth.

## Plan
- Beats come from the transcript (one per sentence). Plan per beat: zoom, B-roll key + mode, callout.
- Assets: one Pinterest query per B-roll beat (key = beat id), concrete and literal to that sentence.
