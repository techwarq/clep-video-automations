---
name: reels
description: Make any vertical short-form video (Reels/TikTok/Shorts) by writing one HTML composition that the reels engine renders to MP4. Specialises in memes, Pinterest-footage edits, motion explainers and edited talking heads. Use for any "make a reel / meme / short / TikTok" request.
---

# Reels — skills index

Any model can make a reel with these files. Two ways to run:

**Automatic** (Muse Spark 1.3 directs; any OpenRouter model via `--model`):
```bash
venv/bin/python -m reels make "a meme about mondays vs fridays"
venv/bin/python -m reels make "how noise cancelling works" --tts lily       # paid voice: asks first
venv/bin/python -m reels make "edit my video" --video ~/me_talking.mp4
```

**By hand** (an agent like Claude Code writes the HTML itself):
```bash
venv/bin/python -m reels new my_reel --style pinterest_edit          # projects/my_reel/ with runtime + plan stub
# edit projects/my_reel/plan.json (beats, assets, content) — see plan.md
venv/bin/python -m reels search my_reel "rainy window aesthetic"     # contact sheet to pick footage by eye
venv/bin/python -m reels pick my_reel b1 <sheet.json> 7              # or: reels add my_reel b1 ~/clip.mp4
venv/bin/python -m reels voice my_reel --draft                       # or --file vo.mp3 / --tts lily (paid)
venv/bin/python -m reels brief my_reel                               # timing + media summary to write against
# write projects/my_reel/comp.html following engine.md + the style skill + its example
venv/bin/python -m reels check my_reel                               # lint + smoke + stills contact sheet
venv/bin/python -m reels render my_reel                              # -> output/my_reel.mp4
```

## Read in this order
1. `plan.md` — prompt → plan.json (style choice, beats, narration, Pinterest queries).
2. `reel-craft.md` — hook, pacing, captions, sound: true for every reel.
3. `engine.md` — the HTML contract and the `R` runtime API. Mandatory before writing comp.html.
4. One style skill + its gold example:

| style | skill | example |
|---|---|---|
| meme | `styles/meme.md` | `examples/meme_vs.html` |
| pinterest edit | `styles/pinterest-edit.md` | `examples/pinterest_editorial.html`, `pinterest_doc.html`, `pinterest_collage.html` |
| motion explainer | `styles/motion-explainer.md` | `examples/motion_explainer.html` |
| talking head | `styles/talking-head.md` | `examples/talking_head.html` |

Examples teach technique. Never copy their words, colours or content into a new reel.

## Cost rules
- Pinterest search/download, Whisper timing, rendering and `--draft` voice are free.
- ElevenLabs voice (`--tts`) is paid: the CLI prints an estimate and asks before calling it.
- Model calls are capped by `REELS_BUDGET_USD` (default $1.00 per run).
