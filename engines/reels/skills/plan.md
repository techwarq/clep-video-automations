---
name: reel-plan
description: How to turn a user's prompt into a reel plan (plan.json) — style choice, beats, narration, Pinterest asset queries, music. Load this when planning, before any HTML is written.
---

# Planning a reel

The plan decides WHAT the reel says and shows. The HTML (written later) decides HOW it moves.

## 1. Pick the style

| style | pick when the prompt… | skill |
|---|---|---|
| `meme` | wants a joke, relatable comparison, POV, "X vs Y", reaction, trend format; 6–10 s | styles/meme.md |
| `pinterest_edit` | wants an aesthetic / story / lifestyle / documentary reel cut from real footage with a voiceover | styles/pinterest-edit.md |
| `motion_explainer` | explains how something works, a concept, numbers, a process, a product — no footage needed | styles/motion-explainer.md |
| `talking_head` | comes with the speaker's own video (`--video`) | styles/talking-head.md |

Anything else ("a countdown reel", "a quote reel", "a listicle") — choose the closest style and say so in
`look`; the engine can render any reel, the styles are where we specialise.

## 2. plan.json schema

```json
{
  "title": "3-6 words",
  "style": "meme | pinterest_edit | motion_explainer | talking_head",
  "narration": "voice | none",
  "beats": [
    {"id": "b1", "text": "exact spoken words for this beat ('' when silent)", "dur": 2.5, "visual": "what the viewer sees"}
  ],
  "assets": [
    {"key": "b1", "query": "2-5 word Pinterest search", "alt": ["backup search"], "kind": "video | image",
     "subject": "optional: what MUST be visible", "use": "where it goes and why"}
  ],
  "music": "warm_indie | warm_drive | deep_minimal | dark_techno | none",
  "look": "2-4 sentences: palette, type, layout idea, the one memorable visual idea",
  "content": {}
}
```

- `beats[].dur` is only used when the reel has no narration (memes); with a voice, timing comes from the words.
- `content` is free-form data the HTML needs (meme rows, list items, numbers, card titles). Keep it real
  and specific to the prompt — never placeholder text.
- Narrated: beat `text` values joined with spaces ARE the voiceover script, word for word.
- Talking head: beats are filled in from the speaker's transcript — plan only visuals/assets/content.

## 3. Writing the narration
- Spoken, punchy, second person, short sentences; ~2.7 words per second of reel.
- Beat 1 is the hook (< 12 words). One idea per beat, 4–18 words.
- End on a payoff line. No emojis, hashtags, stage directions, or "follow for more".

## 4. Pinterest queries that return good footage
- Concrete, filmable things: objects, places, actions, hands, textures, people doing something.
- Add style words that pull quality: `cinematic`, `aesthetic`, `close up`, `slow motion`, `b-roll`, `4k`, `pov`.
- Never abstract nouns ("productivity", "growth", "concept").
- Match what is being said at that moment (literal or a strong metaphor). Vary shots: wide, close-up, hands, motion.
- One asset per beat that needs footage (key = beat id), plus `b3b`-style extras for long beats.
- `subject` only when the shot must show something specific (a landmark, a product type, a famous scene).
- Memes: ONE clip, vertical, calm, no burned-in text — the text is ours.
- Motion explainers usually need no assets at all.
