---
name: reel-meme
description: Meme reels — text-over-footage formats (VS columns, POV, "nobody: / me:", top-bar caption, reaction) on one Pinterest clip, 6–10 s. Use for jokes, relatable comparisons and trend formats.
---

# Meme reels

The joke is the text. The footage is mood, never the punchline's competitor. Gold example:
`examples/meme_vs.html`.

## Formats (pick one per reel)

| format | layout | timing |
|---|---|---|
| **VS columns** | two headers at y≈300, 4–7 short row pairs beneath, left = the bad one, right = the good one | all static for the whole clip (the reference format) or rows pop in every ~0.7 s |
| **POV** | one line top-third: `POV: …`, white with black stroke or on a white pill | static; optional 2nd line lands at ~60 % |
| **nobody: / me:** | two-line setup top, the punch line lands later | `nobody:` at 0, `me:` + action at ~40 % with a pop |
| **top bar** | classic white bar above the footage with black text (Arial / Helvetica bold, 56–64 px), footage below | static |
| **reaction** | setup text on top for 2–3 s, then cut to a second clip (reaction) with the punch line | hard cut + `hit` sfx on the punch |

## Writing the text
- Lowercase or sentence case, casual, specific. Short enough for ONE line per cell (auto-shrink to fit, never wrap
  mid-phrase, never touch the edges — 72 px side margins).
- Rows escalate: the last row is the funniest.
- Specific beats generic: "47 tabs open" > "busy".
- Put the actual rows/lines in `plan.content`, e.g. `{"left": "MONDAY", "right": "FRIDAY", "rows": [["…", "…"]]}`.

## Look
- Text: white `Arial Rounded MT Bold` or `Helvetica Neue` bold with a 2–3 px black stroke (`-webkit-text-stroke` +
  `paint-order: stroke fill`) and a soft shadow; headers 70–80 px, rows 40–48 px.
- A light top/bottom gradient scrim so text reads on bright skies.
- Footage full-bleed (`object-fit: cover`), slow 3–6 % push over the whole clip, looped if short.

## Sound
- Keep the clip's own audio (`R.clipAudio('clip', 0)`) when it's ambient/music; otherwise a bed.
- Formats with a punch moment get one `hit` or `pop` on it. VS columns usually need nothing else.

## Plan
- `narration: "none"`, one beat `{"id": "b1", "dur": 7}` (two for reaction format).
- One asset `{"key": "clip", "kind": "video", "query": "<calm vertical aesthetic scene that fits the vibe>"}`,
  e.g. a beach balcony for a "lazy vs productive" meme, a rainy window for a sad one.
