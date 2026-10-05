"""reels — prompt in, vertical short-form video out.

The engine renders ONE HTML composition (comp.html) per reel, frame by frame, in
headless Chromium. A model (Muse Spark 1.3 by default) plans the reel and writes that
HTML using the skill files in pipeline/skills/; any agent can also write it by hand.

    reels/director   plan -> voice -> Pinterest assets -> compose -> check/review -> render
    reels/assets     Pinterest search/pick, footage frame extraction, voice + word timings
    reels/render     runtime.js (the HTML runtime), capture, audio mix, checks
"""
