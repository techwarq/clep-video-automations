# pipeline_motion: agent plan and context

Last updated 2026-10-02. Read this first in a new session.

## 1. The goal and the user's rules
- Anyone gives a product URL and a request, and gets a top-quality launch film (20–45 s).
- **Quality bar:** the hand-built films in `handbuilt/finals/`: `truecaller_business_chat.mp4`, `notch.mp4`,
  `truemile_v2.mp4`, `maritime_v2.mp4`.
- **Rules:**
  - No voiceover: background music plus sound effects only.
  - Motion is one continuous take: AE-style morphing, **no hard cuts**.
  - Plain, high-quality HTML/CSS UI, true to the brand. No slop. Never a screenshot of the marketing website.
  - Every film is different (story, UI, world, motion). No shared visual kit.
  - **No paid media generation** (video, images, music, SFX) without a cost estimate and a "yes".
    Music and SFX come from `film3/library/`, which is already paid for.
  - **Model cost ≤ $1 per film.** OpenRouter bills a call even if the process is killed mid-call, so count every
    call in full. The $3 cap is per test run, counted across restarts.
  - Plan and explain before big changes. Ask before deleting.
- **Don't force a device.** Understand the product from its website and draw the objects that carry its value. Use
  a phone or laptop only for a moment, when the story needs someone using the app.

## 2. Code that exists now (after the 2026-10-01 cleanup)
```
motion.py                 CLI: python3 motion.py film <name> --url … --request … [--seconds 36]
                               [--model …] [--fix-model …] [--budget 1.00] --yes   (--dry: scripted, $0; --no-render)
film3/agent.py            agent mode: one model writes ONE film.html with tools, iterates, renders. Tools: music_grid,
                          plan (free validator, required before write), set_fonts, read/write/edit_file, check,
                          render_sheet/frame, view_ref, finish. Dry runs work in film3/agent_dry/ (never touch agent/)
film3/llm.py              OpenRouter calls: chat_tools() (agent), text()/json_(); LEDGER (spend), BUDGET (default $1)
film3/check.py            free local checks: film_check() (script errors, hard cuts, text overlap with occlusion, tiny
                          text (one summary line), headline off frame (glyph extents), fallback fonts, words over UI,
                          slow frames) + CRAFT from one low-res scan(): subject < 50% width, large empty areas,
                          frozen holds, nothing on the drop. Calibrated: hand-built truecaller + skeleton pass,
                          the Opus draft fails; full-bleed worlds (notch) are not measured
film3/brandui.py          real product UI: site shots + App Store screenshots + uploads → model crops surfaces,
                          code measures colours → projects/<name>/film3/brand_ui.json + refs/*.png
film3/music.py            library track → whole-bar sections → film bar grid (drop), render spliced music
film3/skills/             what the model reads: 01_motion_rules (no cuts), 02_story (events not features),
                          03_design, 04_sound (+ EVENTS), 05_craft (the ESSENCE of the four finals: what each got
                          right, shared principles, numbers, gotchas; replaces sending any reference code),
                          07_brand_ui (understand the product first), 08_agent (workflow: grid → plan → write → check)
film3/craft/skeleton.html grey-placeholder film that passes check: the dry-run fixture only, never sent to the model
film3/sound.py            free sound pass: window.EVENTS → library cues for every action the agent left silent,
                          drop hit + ½-beat mute, logo sting; motion-peak fallback when no EVENTS
film3/lessons.py          lessons loop: film3/lessons.json, deduped + counted; final-check failures counted per kind;
                          prompt sees the top few; `python3 -m film3.lessons` lists ones ready to become checks
film3/dry.py              scripted model for FILM3_MODEL=dry (whole loop offline; prints first-prompt size)
film3/hybrid.py           EXPERIMENT, not wired into the pipeline: AE-style precomp renderer (see section 6)
bench/                    Dockerfile + run.sh: render benchmark in a container capped like the target VM
film3/runtime/core.js     K helpers (E eases, P, kf, cursorAt, …) — same as handbuilt/v3/lib/core.js
film3/ (from film2)       context.py (site crawl + brand), fonts.py, library.py + library/ (82 SFX, 6 tracks),
                          mix.py (music + SFX mixer, −14 LUFS), render.py + capture.py (60 fps, motion blur), timing.py
director/                 brand.py, site_intel.py, app_logos.py, llm.py, paths.py (used by film3/context)
handbuilt/v3/             notch/ and truecaller/ (film.html, mix.json, assets), lib/core.js, src/ (music + sfx)
handbuilt/v2/             truemile/ and maritime/ (film.html + PAID generated assets/seq), src/ (paid audio)
handbuilt/finals/         the four final hand-built mp4s
projects/<name>/          brand.json, intel.json, intel_pages.md, assets/, renders/; film3/ (brand UI + agent work)
```
Removed in the cleanup: the Remotion engine, templates, the Clep service (not live), the film2 and film3 spec
pipelines, legacy code, and about 10 GB of frames. Nothing was in git, and the user declined a backup.

**Known stale references to fix:** `.claude/skills/launch-film/SKILL.md` and `.claude/skills/notch-film/SKILL.md`
still point at `handbuilt/v3/capture.py`, `mix2.py`, `encode.sh` and `film3/runtime/engine.js`. Those are now
`film3/capture.py`, `film3/mix.py` and `film3/render.encode`, and engine.js is gone. An edit to fix these was
rejected; ask the user before changing them.

## 3. How the hand-built Truecaller Business Chat film was made (the reference craft)
`handbuilt/v3/truecaller/film.html` (344 lines) became `handbuilt/finals/truecaller_business_chat.mp4`:
43.6 s, 60 fps, −13.8 LUFS, $0.

**Process (why it is good):** one craftsperson held the whole film in one file (story, camera, carrier, crowd,
words, timing, sound) and iterated about 10–20 times: render stills, see the exact problem, fix it, re-render.

**Understanding first.** From the site (`projects/truecaller-business/intel*.{json,md}`):
- "Transform everyday messages into meaningful customer moments."
- Use cases: OTPs, order tracking, bill payments, web check-in, feedback.
- Proof: 450M+.
- The film is about MESSAGES becoming trustworthy, not about a phone.

**Story as an event chain, not a feature list:**
1. **Chaos (0–9.6 s).** A phone lock screen where 24 anonymous SMS notifications arrive faster and faster:
   `ARR = [0.3, 0.9, 1.5 … 8.5, 8.65]`. Each new one pushes the stack down 94 px over 0.3 s outCubic, and an
   "N unread" pill climbs. Words beside the phone, as quick scale-in "cut" style text: "Unknown senders." →
   "Short links." → "Unread." → "Ignored."
2. **The one.** A swipe at 9.75 s clears every notification upward (staggered 12 ms, inCubic), except the OTP,
   which glides to the centre. Words: "What if they knew it was really you?"
3. **Push in.** Log-space camera, focus F placed at frame point P, scale 1 → 2.3 by the drop at 14.4 s, then
   ×1.35 inCubic. The phone world blurs and fades: a scale-through.
4. **The card (on the drop).** One `#card` element with a keyframe shape table
   `[t, [w, h, cy, r, headerH, green]]`:
   - notification pill 364×84
   - OTP 820×380
   - ORDER 880×470
   - BILL 820×390
   - CHECK 900×420
   - FEED 820×420
   - ROW 960×112

   The green frame, header and white panel morph continuously. Each use case is a layer cross-revealed inside it
   over 0.24 s: opacity, scale 0.95→1, blur 8→0. The card world is scaled 1.32 so the UI reads big. Labels sit
   above it: "One-tap OTPs.", "Order tracking.", …
5. **A real action in every card** (a touch dot plus ripple at TAPS 17.4 / 20.7 / 22.9 / 25.1 / 27.5 s):
   - COPY OTP → "OTP COPIED ✓", which turns green;
   - order tracker steps light up and the line fills;
   - PAY NOW → "PAID ✓", and the due date becomes "Paid · receipt sent";
   - the seat 14A slides in;
   - five stars fill 75 ms apart with a spring.

   A sticky "Pinned until used" pill appears too.
6. **Scale.** The card morphs into an inbox ROW (29.4 s), other verified rows appear around it, and the camera
   pulls back (1.32 → 1.0). The rows plus the card collapse into a point that becomes a 450M+ counter (counting,
   250 px), then "people who see it's really you".
7. **Breadth.** Five feature words punch in, one per 0.96 s, each with a scale punch.
8. **Name.** "Every message, verified." → the real logo (`projects/truecaller-business/assets/brand/logo.png`),
   then "Business Chat", then the URL.

**Look:** Poppins 400–800 localized (`truecaller/assets/fonts.css`). Truecaller green #19a14b, blue tick #0a6cff.
An off-white #f3f6fb field with drifting dots that pulse on the beat after the drop.

**Music first:** `src/music/truecaller.mp3`, spliced from `warm_indie_100` (100 bpm, bar 2.4 s) at bar boundaries:
4.816+14.4 s, 19.216+9.6 s ×2, 24.016+4.8 s and 28.816+4.8 s, for 43.2 s with the drop at 14.4 s (the card's
arrival). Every scene starts on a downbeat, arrivals land on beats, staggers on 8ths.

**Sound:** `truecaller/mix.json` holds the music (gain, offset, automation, duck) and timed library cues. There is
a pop per notification (pitch rising), a whoosh on the swipe, an iris hit on the drop, felt clicks on taps,
success sounds on results, and a logo sting.

**Render:** capture at 60 fps with sub-frame motion blur (`--sub 2`) on 6 workers, about 6 min, then encode H.264
and mux AAC.

**Gotchas fixed while building:**
- core.js `$` is getElementById, so the film uses a local `$` that also takes `#` selectors;
- `show()` cleared an inline `display:flex`, fixed with a CSS rule;
- canvas arc radius must be ≥ 0;
- fonts must be awaited in boot;
- encode only after all frames exist.

## 4. What was tried, and what was learned
| Attempt | Result | Lesson |
|---|---|---|
| film2: Muse writes the whole film in one shot | bad | a cheap model writing one huge file blind fails |
| film3 spec pipeline, Muse (spec → engine morphs → many small calls) | ~$0.04–0.07/film, zero cuts, but a **slideshow** | split calls lose coherence; a spec format is always one feature behind |
| + brand UI (site + App Store crops), devices, groups, actions, validator | better brand truth, still flat | |
| same pipeline, Sonnet 5.5 | better story, ~$2.25 + $0.40 failed calls | expensive, still a slideshow |
| **agent mode, Opus 5.5** (one film.html + tools) | **right idea from the website, no phone**, but small subjects and too much empty space; $1.38 total and no fix rounds | turn 1 cost $0.65 (19k thinking + 52k uncached prompt); the stopped call was still billed $0.35 |

Other facts:
- **Truecaller test hygiene:** never show a same-brand worked example or skill line; the model copies it.
  `agent.pick_refs` excludes the brand, and `system_prompt` filters out lines that mention it.
- **Fonts:** the brand's own font files can be broken (serif fallback). `set_fonts` now uses Google Fonts first.
- **Muse Spark** (`meta/muse-spark-1.3-contributor`): $0.10/M in, $0.20/M out.
- **Sonnet 5.5:** $2/M in, $10/M out.
- **Opus 5.5:** $4/M in, $20/M out.
- **Sonnet quirks:** it needs `reasoning.effort` set, a long timeout (900 s), and ≥ 32k max_tokens, otherwise its
  replies come back empty.

## 5. Agent plan: hand-built quality at ≤ $1 per film

### Done, but not yet tested with a real model
- `FILM3_EFFORT` defaults to `low`; a predictive budget guard; `--fix-model` (Opus writes, Sonnet fixes).
- If mix.json is missing at the end, the render falls back to music only.

### Done 2026-10-01 (all at $0, verified with local renders and a dry run)
- **Free craft checks** (step 3): subject size, empty areas, frozen holds, payoff on the drop, fallback fonts,
  words over UI. Calibrated so the hand-built Truecaller film and the skeleton pass and the Opus draft fails.
  Thresholds: subject < 0.50 width for > 0.5 s; empty (fill < 0.12 or ≥ 6 of 12 cells) for > 1 s; frozen
  ≥ 1.2 s; drop peak < 2.5× median.
- **Cheaper first turn** (step 2): no reference code is sent (`FILM3_REFS=0`); 05_craft.md holds the essence of
  the four finals. System prompt 12.4–14.5k → 7.8k tokens. The required free `plan` tool replaces long hidden
  reasoning: it validates the payoff on the drop, beats on the grid, subject ≥ 55%, carrier ≥ 1000 px, a real
  action, and ≤ 8 words per beat.
- **No reference code is sent to the model** (user's decision): 05_craft.md is an ESSENCE file of what each
  final got right, plus shared principles. The section about the same brand as the film being made is dropped
  (`<!-- ref:brand -->` tags), so a Truecaller test never sees the Truecaller story.
- **Lessons loop** (step 4): lessons.py (dedupe, counts, final-check failure kinds, promote list).
- **Sound by default** (step 5): sound.py fills cues from window.EVENTS at render time.
- **Dry run:** `python3 motion.py film truecaller-business --url https://business.truecaller.com/ --dry` takes
  1.4 min, makes 7 scripted turns, costs $0.000, and renders 1080p60 at −13.9 LUFS.

### Next steps, in order
1. **One paid test, when there is credit** (≈ $0.6–0.9): `--model anthropic/claude-opus-5.5 --fix-model
   anthropic/claude-sonnet-5.5 --budget 1`. Report the cost per turn. Compare it with
   `handbuilt/finals/truecaller_business_chat.mp4`.
   - Note: switching to the fix model starts a new prompt cache (one cache write of about 40k tokens on Sonnet,
     about $0.12).
   - Note: a real run deletes `projects/<name>/film3/agent/` first (the old Opus draft lives there now).
2. Grow the lessons and checks from that run (`python3 -m film3.lessons`).
3. Then scale down: Sonnet as the writer, and Muse for mechanical fix rounds, measuring against the finals each
   time.
4. Possible later: a vector DB of craft snippets, only if the lessons plus the craft notes stop being enough.

## 6. Rendering, scale and cost (decided or measured on 2026-10-02)

**Target.** A 40 s film for **< $1 of model cost** is "good". The estimate with Opus writing and Sonnet fixing is
about $0.75–0.85: turn 1 $0.14, writing $0.20, switching cache to Sonnet $0.12, 8–10 fixes $0.25–0.35. This is
unverified until one paid run (needs credits). Rendering costs about 1–3 cents per film.

**Target machine.** One VM with about 4 vCPU and 4 GB (budget).
- **Measured:** today's renderer (`film3/capture.py`, 3 workers, 60 fps, sub 2) gets **killed for lack of
  memory** in a container capped at 4 CPU / 4 GB (signal 9 after 1,431 of 2,616 frames of the Truecaller film).
- About 1 GB per worker: Chromium at 1080p, the Playwright driver, and float32 screenshot buffers.
- On 4 GB: use ≤ 2 browsers, add 2 GB of swap, slim the worker (JPEG capture, uint8/uint16 buffers, restart
  the browser every few hundred frames).
- **Never run renders in parallel per job.** Use one global queue with a fixed number of browser slots per
  machine (2–3 on 4 GB), one render at a time. Agent/model phases (network-bound) can run concurrently with
  async.
- Inside a worker, threading helps only as a pipeline: one thread owns the page (seek + screenshot), threads
  decode/blur/encode (PIL, numpy and cv2 release the GIL), and one thread writes or pipes to ffmpeg. Estimated
  20–40% faster; not built.

**Hybrid renderer (film3/hybrid.py), prototype, works on any film page unchanged.**
- Passes: discover the animated elements (layers), record each sub-frame's layer box, scale, opacity, blur,
  rounded clip and content key (no screenshots), rasterize each unique layer once (2× where the camera
  magnifies), then composite natively with OpenCV (warp, Gaussian blur, opacity, clip, motion blur).
- Fidelity on the Truecaller film: **33–46 dB PSNR** against browser frames; zoomed crops look identical.
  87 layers, about 200 unique rasters.
- Bugs fixed: ancestors' overflow clipped moved layers; a layer's size comes from its parent, so the key
  includes offsetWidth×offsetHeight; rasters cropped to their visible pixels; the cache holds uint8.
- Approximations: translate/scale only (no rotation), group opacity/blur applied per layer, backdrop-filter
  ignored.
- Local speed (M5, not capped): composite about 45 ms per sub-frame, record about 22 ms per sub-frame per page.
- **Not yet measured:** the capped-container time and peak memory, against the browser path with retries.
  Next: run `bench/` both ways (`docker build -t motion-bench bench/`, then
  `docker run --cpus=4 --memory=4g --memory-swap=4g --shm-size=512m -v $PWD:/work -v <out>:/out -v
  $PWD/bench/run.sh:/run.sh motion-bench /run.sh browser|hybrid`).
- Ideas if it is worth adopting: record at frame rate and interpolate sub-frames; dirty-tracking of layer keys
  with a MutationObserver.
- **Docker hygiene:** the user runs other containers on this Mac (e.g. a Postgres for another project). Only
  stop containers filtered by `--filter ancestor=motion-bench`; never stop by a raw `docker ps` list.

**Hosting for about 1,000 users** (about 3 films each per month, so about 3,000 films/month; prices
approximate, from memory, not checked live):
- Hetzner 8 vCPU / 16 GB costs about €15–30/month, has no free tier, bills hourly with a monthly cap, and has
  sometimes given referral credit.
- Oracle Cloud Always Free: 4 ARM cores and 24 GB RAM at $0. ARM Chromium works; capacity can be scarce.
- Others: DigitalOcean 8 vCPU / 16 GB about $96; GCP e2-highcpu-8 about $145; AWS c7g.2xlarge about $210 (spot
  60–70% less).
- One 8 vCPU box ≈ 2 concurrent renders ≈ 20–30 films/hour (estimate). That covers the average load; add boxes
  hourly when the queue is long.
- Monthly: servers €30–90, storage €5–10, **model up to about $3,000**. Model cost per film is the lever.
- Not built for real users: job queue and workers with a browser pool and retries, accounts/API/job status,
  video storage and links, per-user spend limits.

### Open questions for the user
- Whether to keep the paid v2 source media (`handbuilt/v2/*/assets|seq|src`, about 500 MB).
- Whether to keep old brand projects in `projects/` (clep-*, talo, factech, …), which hold only inputs and renders.
