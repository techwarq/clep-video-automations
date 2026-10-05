"""A scripted stand-in for the model (FILM3_MODEL=dry): exercises the whole agent loop for $0, with no network.

It plays the workflow of 08_agent.md with the annotated skeleton as the film: music_grid → a plan that breaks the
rules (to prove the validator) → a good plan → set_fonts → write → check → sheet → mix.json → finish. It also
reports how big the real first prompt is, so prompt-cost changes can be measured without a paid call.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOK = 3.8                                                    # ≈ characters per token for English + code


def _call(i: int, name: str, args: dict) -> dict:
    return {"id": f"dry{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


BEATS = [
    {"t0": 0, "t1": 4.8, "event": "arrivals pile up, faster and faster", "subject": "the stack", "subject_width_pct": 62, "words": "‹the problem›"},
    {"t0": 4.8, "t1": 7.2, "event": "a swipe clears all but one; camera pushes in", "subject": "the one", "subject_width_pct": 70, "words": "‹what if…›", "action": "swipe"},
    {"t0": 7.2, "t1": 12.0, "event": "the one becomes the carrier, state 1; tap → done", "subject": "carrier", "subject_width_pct": 67, "words": "‹what state 1 does›", "action": "tap ACTION → DONE ✓"},
    {"t0": 12.0, "t1": 16.8, "event": "carrier morphs to state 2; tap fills the result", "subject": "carrier", "subject_width_pct": 73, "words": "‹what state 2 does›", "action": "tap → bar fills"},
    {"t0": 16.8, "t1": 19.2, "event": "collapse into the proof number", "subject": "counter", "subject_width_pct": 60, "words": "‹what the number proves›"},
    {"t0": 19.2, "t1": 21.6, "event": "logo", "subject": "logo", "subject_width_pct": 30, "words": "‹logo›"},
]
PLAN = {"understanding": "dry run: structure only", "world": "off-white field with drifting dots", "signature": "the one item becomes everything",
        "carrier": {"what": "one card", "states": [{"name": "item", "w": 1440, "h": 240}, {"name": "state 1", "w": 1280, "h": 640},
                                                   {"name": "state 2", "w": 1400, "h": 700}, {"name": "row", "w": 1400, "h": 220}]},
        "beats": BEATS, "payoff_t": 7.2}
BAD = {**PLAN, "payoff_t": 3.0, "carrier": {"what": "one card", "states": [{"name": "tiny", "w": 600, "h": 300}]},
       "beats": [{**b, "subject_width_pct": 30, "action": ""} for b in BEATS]}


def turn(messages: list, tools: list) -> dict:
    n = sum(1 for m in messages if m.get("role") == "assistant")
    if n == 0:
        sys_chars = sum(len(c.get("text", "")) for c in messages[0]["content"])
        user = messages[1]["content"]
        u_chars = sum(len(c.get("text", "")) for c in user if c.get("type") == "text")
        imgs = sum(1 for c in user if c.get("type") == "image_url")
        print(f"[dry] first prompt: system ≈ {sys_chars / TOK / 1000:.1f}k tokens, brief ≈ {u_chars / TOK / 1000:.1f}k tokens, "
              f"{imgs} images (≈ {imgs * 1.6:.1f}k tokens), tools ≈ {len(json.dumps(tools)) / TOK / 1000:.1f}k tokens", flush=True)
    skel = (HERE / "craft" / "skeleton.html").read_text()
    mix = {"track": "warm_indie_100", "sections": [[6, 14]], "duration": 21.6, "music_db": -3,
           "cues": [{"t": 7.16, "id": "warm_iris", "gain": -3}]}
    script = [
        [("music_grid", {"track": "warm_indie_100", "sections": [[6, 14]]})],
        [("plan", BAD)],
        [("plan", PLAN)],
        [("set_fonts", {"display": "Inter", "ui": "Inter"}), ("write_file", {"path": "film/index.html", "content": skel})],
        [("write_file", {"path": "film/mix.json", "content": json.dumps(mix)}), ("check", {})],
        [("render_sheet", {"times": [1, 4.6, 6.4, 7.4, 10, 15, 18, 20.5]})],
        [("finish", {"summary": "dry run of the skeleton", "lessons": [
            "Plan the payoff on the drop before writing; the validator rejects anything else.",
            "Count to a number with a fixed digit count, or the layout jumps like a cut."]})],
    ]
    calls = script[min(n, len(script) - 1)]
    return {"message": {"role": "assistant", "content": f"(dry turn {n + 1})",
                        "tool_calls": [_call(i, k, a) for i, (k, a) in enumerate(calls)]}}
