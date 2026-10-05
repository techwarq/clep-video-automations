"""Plan + project data -> comp.html, then make it pass the checker and a visual review.

    write()   the style skill + engine contract + a gold example -> a first composition
    repair()  lint + smoke problems go back to the model until clean (or rounds run out)
    review()  stills at each beat -> the model looks at them against the style checklist -> one fix pass
"""

from __future__ import annotations

from reels import llm, skills
from reels.director.plan import dumps
from reels.render import check

WRITE = """Write comp.html for this reel.

PLAN
{plan}

TIMING + MEDIA (from data.js — use these exact beat ids and media keys)
{brief}

GOLD EXAMPLE for this style (technique only — do not copy its words, colours or content):
```html
{example}
```

Return the complete file in ONE ```html block."""

FIX = """The composition has problems. Fix ALL of them and return the complete corrected file in ONE ```html block.

PROBLEMS
{problems}

CURRENT FILE
```html
{html}
```"""

REVIEW = """These are stills from the reel at the times shown (t = seconds), in order. The style rules and the
plan are in your context. Judge like a demanding short-form editor:
- Is text readable on every frame (size, contrast, never cut off or overlapping the edges/each other)?
- Is the frame full and intentional (no empty areas, no tiny elements floating in space, no broken layout)?
- Does each frame show what its beat says? Does the hook frame grab attention?
- Does it follow the style skill's look?

Return ONLY JSON: {{"ok": true|false, "fixes": ["specific, actionable change", ...]}} (max 6 fixes, [] if ok)."""


def _system(style: str) -> str:
    return skills.compose_context(style)


def write(project, plan: dict, model: str | None = None) -> str:
    msg = WRITE.format(plan=dumps(plan), brief=project.summary(),
                       example=skills.pick_example(plan["style"], plan.get("look", "")))
    reply = llm.chat([{"role": "system", "content": _system(plan["style"])}, {"role": "user", "content": msg}],
                     tag="compose", model=model, max_tokens=24000, temperature=0.5)
    html = llm.extract_html(reply)
    project.html.write_text(html)
    return html


def problems(project) -> list[str]:
    html = project.html.read_text()
    found = check.lint(html, project.media)
    if not found:   # the smoke test needs a page that at least passes lint
        found = check.smoke(project.html, project.write_data()["dur"])
    return found


def repair(project, plan: dict, model: str | None = None, rounds: int = 3) -> list[str]:
    found = problems(project)
    for r in range(rounds):
        if not found:
            print("[compose] checks pass")
            return []
        print(f"[compose] fixing {len(found)} problem(s), round {r + 1}: " + "; ".join(found)[:300])
        _fix(project, plan, found, model)
        found = problems(project)
    if found:
        print("[compose] still failing: " + "; ".join(found)[:400])
    return found


def _fix(project, plan: dict, found: list[str], model: str | None) -> None:
    reply = llm.chat([{"role": "system", "content": _system(plan["style"])},
                      {"role": "user", "content": FIX.format(problems="\n".join(f"- {p}" for p in found),
                                                             html=project.html.read_text())}],
                     tag="fix", model=model, max_tokens=24000, temperature=0.3)
    try:
        project.html.write_text(llm.extract_html(reply))
    except ValueError:
        print("[compose] fix reply had no html block — keeping the previous file")


def review_times(project) -> list[float]:
    reel = project.write_data()
    times = [round(b["t0"] + min(0.9, (b["t1"] - b["t0"]) * 0.6), 2) for b in reel["beats"]]
    return [min(t, reel["dur"] - 0.05) for t in ([0.3] + times)][:10]


def review(project, plan: dict, model: str | None = None) -> list[str]:
    """One look-and-fix pass. Keeps the old file if the fix breaks the checks."""
    times = review_times(project)
    files = check.stills(project.html, times, project.root / "stills")
    content = [llm.text_part(f"PLAN\n{dumps(plan)}\n\n{REVIEW}")]
    for t, f in zip(times, files):
        content += [llm.text_part(f"t = {t:.2f}s"), llm.image_part(f)]
    try:
        verdict = llm.chat_json([{"role": "system", "content": _system(plan["style"])},
                                 {"role": "user", "content": content}],
                                tag="review", model=model, max_tokens=3000, temperature=0.2)
    except Exception as e:
        print(f"[review] skipped ({str(e)[:120]})")
        return []
    fixes = [str(f) for f in (verdict.get("fixes") or [])][:6] if isinstance(verdict, dict) else []
    if not fixes:
        print("[review] looks good")
        return []
    print("[review] " + " | ".join(fixes))
    before = project.html.read_text()
    _fix(project, plan, [f"visual review: {f}" for f in fixes], model)
    if repair(project, plan, model, rounds=2):
        print("[review] fix broke the checks — restoring the reviewed version")
        project.html.write_text(before)
    return fixes
