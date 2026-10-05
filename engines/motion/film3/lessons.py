"""The lessons loop: every run teaches the next one, and the file stays short.

- the agent's own lessons (finish(lessons)) are merged into near-duplicates, each counting how often it recurs;
- the final check's failures are counted per kind, so recurring misses surface first in the next prompt;
- `python3 -m film3.lessons` prints the lessons that recur often enough to become a free check or a skill line.

Stored in film3/lessons.json; the prompt sees only the top few (cheap).
"""
from __future__ import annotations

import json
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import List

HERE = Path(__file__).resolve().parent
STORE = HERE / "lessons.json"
# check report line → (kind, the fix to remember)
CHECK_KINDS = [
    ("main subject small", "make the main subject 60–80% of the frame width (scale the carrier, push the camera)"),
    ("large empty areas", "fill the frame: the subject or its world, never a small object on an empty field"),
    ("frozen at", "never hold still: a slow camera or world drift under every hold"),
    ("nothing big happens on the drop", "land the payoff exactly on the drop bar"),
    ("words over UI", "words get their own clear space, never on top of the product UI"),
    ("which is not loaded", "only use the families set_fonts returned"),
    ("HARD CUTS", "morph or scale-through between scenes; never swap content in one frame"),
    ("SCRIPT ERRORS", "run check right after writing; fix script errors first"),
    ("text overlaps text", "words and UI text must not overlap; cross-fade one out before the next arrives"),
    ("headline runs off the frame", "measure headline width; keep 80 px margins"),
]


def load() -> dict:
    try:
        return json.loads(STORE.read_text())
    except Exception:
        return {"lessons": [], "checks": {}}


def save(db: dict):
    STORE.write_text(json.dumps(db, indent=1, ensure_ascii=False))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def add(film: str, lessons: List[str], db: dict = None) -> dict:
    db = db or load()
    for l in (x.strip() for x in lessons if x and x.strip()):
        n = _norm(l)
        hit = next((e for e in db["lessons"] if SequenceMatcher(None, _norm(e["text"]), n).ratio() > 0.72), None)
        if hit:
            hit["count"] += 1; hit["last"] = time.strftime("%Y-%m-%d")
            hit["films"] = sorted(set(hit["films"]) | {film})
            if len(l) < len(hit["text"]):                    # keep the tighter wording
                hit["text"] = l
        else:
            db["lessons"].append({"text": l, "count": 1, "films": [film], "last": time.strftime("%Y-%m-%d")})
    save(db)
    return db


def record_checks(report: str, film: str = "") -> dict:
    """Count which kinds of problem the FINAL film still had (what the agent did not manage to fix)."""
    db = load()
    for key, _ in CHECK_KINDS:
        if key in report:
            c = db["checks"].setdefault(key, {"count": 0, "films": []})
            c["count"] += 1; c["films"] = sorted(set(c["films"]) | ({film} if film else set()))
    save(db)
    return db


def prompt_text(limit: int = 12) -> str:
    db = load()
    out = []
    rec = sorted(db["checks"].items(), key=lambda kv: -kv[1]["count"])
    fix = dict(CHECK_KINDS)
    if rec:
        out.append("Past films most often shipped with these problems (fix them before you look):")
        out += [f"- {fix[k]} (×{v['count']})" for k, v in rec[:5]]
    ls = sorted(db["lessons"], key=lambda e: (-e["count"], e["last"]), reverse=False)[:limit]
    if ls:
        out.append("Lessons from earlier films:")
        out += [f"- {e['text']}" + (f" (×{e['count']})" if e["count"] > 1 else "") for e in ls]
    return "\n".join(out) or "(none yet)"


def promote(min_count: int = 3) -> List[str]:
    """Lessons that recur often enough to become a free check (check.py) or a skill line. Printed for a human."""
    db = load()
    return [f"{e['count']}× {e['text']}  [{', '.join(e['films'][:4])}]" for e in db["lessons"] if e["count"] >= min_count]


if __name__ == "__main__":
    print(prompt_text(40))
    p = promote(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
    print("\nReady to become a check or a skill line:\n" + ("\n".join(p) if p else "(none yet)"))
