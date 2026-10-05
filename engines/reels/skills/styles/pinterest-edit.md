---
name: reel-pinterest-edit
description: Edited reels cut from Pinterest footage under a voiceover — editorial (serif phrases, location tags), documentary (graph paper, framed footage, yellow stamps) or commentary collage (yellow outlined headline, rounded footage cards, reaction stickers). Use for aesthetic, story, lifestyle, recap and personality reels.
---

# Pinterest edit reels

Real footage pulled from Pinterest, cut fast to a voiceover, with designed type on top. Three proven looks —
pick one, then make it this reel's own (palette, tags, graphics from the topic).

## Look A — Editorial (`examples/pinterest_editorial.html`)
- Full-bleed footage, gentle grade (contrast 1.04, saturation 1.06), vignette, faint grain.
- Captions are big `Instrument Serif` phrases (140–170 px, 1–3 words) that HOP between anchor spots around the
  frame per phrase; spoken word full white, the rest 45 %; emphasis words italic.
- Small location/time tags top-left (`● San Francisco`, `● 7:40 AM`, `● Day 1`) — a cream pill with a red dot.
- One paper title card (cream, italic serif headline + small tracked caps + a drawn rule) at the turn of the story.
- Music: `warm_indie` / `warm_drive`, soft whoosh only on beat changes. Calm but never static.

## Look B — Documentary (`examples/pinterest_doc.html`)
- Grounds alternate beat to beat: graph paper → black/night grid → paper. Never two identical looks in a row.
- Footage is never raw full-bleed: framed (dark rounded frame + corner brackets), split (two stacked panels),
  or letterboxed (16:9 band on black).
- Yellow `#FFD60A` is the only accent: stamp words in yellow boxes that slam in on spoken words
  (`NEW IDEA.`), yellow emphasis in captions (yellow text on dark, yellow marker on paper).
- Type-slam beats: black screen, one huge line at a time on its word, last line yellow.
- Hand-built graphics for abstract lines: a countdown card, a progress bar, app windows piling up,
  a runaway dot that freezes — built in HTML/SVG, driven by word times.
- Callbacks: bring an earlier graphic back changed at the end (the runaway dot becomes one straight line).
- Captions: Avenir Next 800, uppercase, 2–3 words, bottom (y≈1720) or under the band.

## Look C — Commentary collage (`examples/pinterest_collage.html`)
For recaps, "how X became a legend", sports/celebrity/news explainers — the YouTube-essay look.
- Off-white canvas with a faint dot grid; a giant yellow headline with a thick black outline at the top
  (Arial Black, auto-shrunk to one line) that slams in at every beat — 1–3 words: `THE ROOKIE`, `DAY ONE`.
- Footage sits in white-bordered rounded cards with soft shadows: 1 big card, 2 stacked, or the
  2-up + 1-below collage; cards pop in one after another (0.35 s apart) with small tilts.
- A meme reaction sticker (shocked face, side-eye animal, crying fan) slides in from the edge on the
  punchline word — one or two per reel, never more.
- Captions: black Avenir 900 uppercase, the spoken word on a yellow marker.
- Queries name the real subject + moment (`kimi antonelli mercedes f1`, `f1 podium celebration`);
  reaction queries are meme-ish (`shocked monkey meme`, `surprised cat face`). Use `subject` for real people.

## Cutting
- Every beat starts a shot; beats longer than ~1.4 s cut again on a word onset (cycle the beat's keys).
- 4–6 % punch on every cut, then a slow push/drift/pull/rise — rotate moves, never repeat.
- Start clips ~0.3 s in (first frames of Pinterest clips are often fades or text).
- A footage beat with no asset falls back to a type/graphic beat — never an empty frame.

## Plan
- `narration: "voice"`, 5–10 beats, one footage asset per beat (`key` = beat id; add `b2b` for long beats).
- Put tags/stamps/card titles in `plan.content` keyed by beat id.
- Queries: concrete + aesthetic words (`laptop desk morning aesthetic`, `city night timelapse cinematic`).
