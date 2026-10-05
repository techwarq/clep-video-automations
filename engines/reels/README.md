# pipeline — the reels engine

Prompt in, vertical short-form video out (Reels / TikTok / Shorts, 1080×1920).

One engine renders any reel. At runtime a model writes ONE HTML composition per reel
(`comp.html`); headless Chromium renders it frame by frame; ffmpeg mixes the voice, music and SFX.
The craft lives in **skills** (markdown + gold example HTML) that any model can read. Muse Spark 1.3
is the default director. We specialise in four styles:

| style | what | gold example |
|---|---|---|
| `meme` | text-over-footage formats (VS columns, POV, top bar…) on one Pinterest clip | `skills/examples/meme_vs.html` |
| `pinterest_edit` | voiceover cut over Pinterest footage — editorial or documentary look | `skills/examples/pinterest_editorial.html`, `pinterest_doc.html` |
| `motion_explainer` | one-take motion graphics: one object morphs through every idea | `skills/examples/motion_explainer.html` |
| `talking_head` | your video, edited: punch-ins, B-roll, callouts, karaoke captions | `skills/examples/talking_head.html` |

## Quick start

```bash
cd pipeline
python3 -m venv venv && venv/bin/pip install -r requirements.txt && venv/bin/playwright install chromium
cp .env.example .env            # add OPENROUTER_API_KEY

venv/bin/python -m reels make "meme: introverts vs extroverts at a party"
venv/bin/python -m reels make "explain how a credit score works" --tts lily     # paid voice, asks first
venv/bin/python -m reels make "turn this into a reel" --video ~/talking.mp4
```

Without `--tts` / `--voice-file`, narrated reels render as a silent draft timed at reading speed —
check the cut, then re-run `voice` + `render` on the same project with real audio.

## How a reel is made (`reels/director/run.py`)

```
prompt ─► plan.json        model + skills/plan.md: style, beats, script, Pinterest queries, music
       ─► voice            ElevenLabs (paid, confirmed) | your recording + Whisper | silent draft
       ─► assets           Pinterest search → rank → vision screen (thumbnails) → download → JPEG frames
       ─► comp.html        model + skills/engine.md + style skill + gold example
       ─► check / repair   lint + live smoke test; problems go back to the model
       ─► review           stills per beat → model critiques against the style → one fix pass
       ─► render           parallel Chromium capture → H.264 + audio mix (-14 LUFS) → output/<name>.mp4
```

A typical run costs well under $0.05 in model calls (`REELS_BUDGET_USD` caps it, default $1).

## Writing a reel by hand (any agent)

Read `skills/SKILL.md`. In short: `reels new` → edit `plan.json` → `reels search/pick/add` footage →
`reels voice` → `reels brief` → write `comp.html` → `reels check` → `reels render`.

## Layout

```
pipeline/
  reels/                     the engine (python -m reels)
    __main__.py              CLI
    config.py  llm.py        settings, OpenRouter client with cost ledger
    project.py               one reel = projects/<name>/ (plan, words, media, data.js, comp.html)
    skills.py                loads skill files as model context
    director/  plan.py compose.py run.py
    assets/    pinterest.py picker.py media.py voice.py
    render/    runtime.js browser.py capture.py audio.py check.py
  skills/                    model-facing craft — SKILL.md, plan.md, reel-craft.md, engine.md,
                             styles/*.md, examples/*.html
  library/                   fonts/, music/, sfx/ used by compositions
  projects/  output/  .cache/   generated (gitignored)
```

## The HTML contract (short)

`comp.html` loads `data.js` then `runtime.js`, and draws everything inside `R.scene(t => …)`.
No timers, CSS animation, `<video>`/`<audio>` or `Math.random` — every frame is a pure function of `t`.
Footage is `<img>` driven by `R.show(img, key, seconds)`; sound is declared with `R.music`, `R.sfx`,
`R.clipAudio`. Full reference: `skills/engine.md`.
