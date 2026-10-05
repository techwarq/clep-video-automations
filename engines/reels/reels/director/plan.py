"""Prompt -> plan.json (style, beats, narration, Pinterest assets, music, content).

The model plans with plan.md + reel-craft.md + every style skill as context.
Python enforces the contract: valid style, unique beat ids, asset keys, library music,
and — for talking heads — beats fixed to the speaker's real sentences.
"""

from __future__ import annotations

import json
import re

from reels import llm, skills
from reels.render.audio import library

PLAN_USER = """Plan a reel for this request:

{prompt}

{extra}
Return ONLY the plan.json object."""


def sentences(words: list[dict]) -> list[str]:
    """Group transcript words into sentence beats (long sentences split at a comma)."""
    out, cur = [], []
    for w in words:
        cur.append(w["w"])
        n = len(cur)
        if re.search(r"[.!?]$", w["w"]) or (n >= 14 and re.search(r"[,;:]$", w["w"])) or n >= 22:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def make(prompt: str, style: str | None = None, seconds: int | None = None,
         transcript: list[dict] | None = None, model: str | None = None) -> dict:
    extra = []
    if style:
        extra.append(f"Style is fixed: {style}.")
    if seconds:
        extra.append(f"Target length: about {seconds} seconds.")
    fixed = sentences(transcript) if transcript else None
    if fixed:
        extra.append("This is a talking-head reel. The speaker's sentences are fixed beats, in order "
                     "(ids b1..bN, keep text exactly):\n" +
                     "\n".join(f"b{i + 1}: {s}" for i, s in enumerate(fixed)) +
                     "\nPlan only visuals, B-roll assets and content for them.")
    lib = library()
    extra.append(f"Library music: {', '.join(lib['music'])} (or none).")
    raw = llm.chat_json(
        [{"role": "system", "content": skills.planning_context()},
         {"role": "user", "content": PLAN_USER.format(prompt=prompt, extra="\n".join(extra) + "\n")}],
        tag="plan", model=model, max_tokens=8000, temperature=0.7)
    plan = validate(raw, style, fixed)
    print(f"[plan] {plan['style']} · {len(plan['beats'])} beats · {len(plan['assets'])} assets — {plan['title']!r}")
    return plan


def validate(raw: dict, style: str | None = None, fixed: list[str] | None = None) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("plan is not a JSON object")
    st = style or raw.get("style")
    if st not in skills.STYLES:
        st = "talking_head" if fixed else "pinterest_edit" if raw.get("assets") else "motion_explainer"
    beats = []
    for i, b in enumerate(raw.get("beats") or []):
        if not isinstance(b, dict):
            continue
        beats.append({"id": f"b{i + 1}", "text": " ".join(str(b.get("text") or "").split()),
                      "visual": str(b.get("visual") or ""), "dur": float(b.get("dur") or 0) or None})
    if fixed:   # talking head: the speaker's words win, model visuals map by position
        beats = [{"id": f"b{i + 1}", "text": s, "visual": beats[i]["visual"] if i < len(beats) else ""}
                 for i, s in enumerate(fixed)]
    if not beats:
        raise ValueError("plan has no beats")
    narration = "voice" if (fixed or any(b["text"] for b in beats)) and raw.get("narration") != "none" else "none"
    if narration == "none":
        for b in beats:
            b["dur"] = b.get("dur") or 2.5
    else:
        for b in beats:
            b.pop("dur", None)
    # memes hold one clip for the whole reel; cut-based styles only need a few seconds per shot
    min_s = sum(b.get("dur") or 0 for b in beats) * 0.8 if st == "meme" else 3.0
    assets, seen = [], set()
    for a in raw.get("assets") or []:
        if not isinstance(a, dict) or not str(a.get("query") or "").strip():
            continue
        key = re.sub(r"[^\w-]", "_", str(a.get("key") or f"a{len(assets) + 1}"))
        if key in seen or key == "face":
            continue
        seen.add(key)
        assets.append({"key": key, "query": str(a["query"]).strip(),
                       "alt": [str(q) for q in (a.get("alt") or []) if str(q).strip()][:2],
                       "kind": "image" if a.get("kind") == "image" else "video",
                       "subject": str(a.get("subject") or ""), "use": str(a.get("use") or ""),
                       "min_s": min_s,
                       "fallback": str(raw.get("topic_query") or "")})
    music = raw.get("music")
    if music not in library()["music"]:
        music = "none" if music == "none" else library()["music"][0]
    return {"title": str(raw.get("title") or "reel")[:60], "style": st, "narration": narration,
            "beats": beats, "assets": assets, "music": music, "look": str(raw.get("look") or ""),
            "content": raw.get("content") if isinstance(raw.get("content"), dict) else {},
            "tail": 0.8 if narration == "voice" else 0.0}


def script(plan: dict) -> str:
    return " ".join(b["text"] for b in plan["beats"] if b["text"]).strip()


def dumps(plan: dict) -> str:
    return json.dumps({k: v for k, v in plan.items() if k != "tail"}, indent=1)
