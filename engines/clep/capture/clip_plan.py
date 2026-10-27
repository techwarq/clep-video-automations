from __future__ import annotations

import json
from pathlib import Path

DICT_OPTIONS = ("intro", "look", "outro")
LIST_OPTIONS = ("private",)
TEXT_OPTIONS = ("goal", "audience", "voiceover")
STEP_NOTES = ("story", "moment", "effect")
KEY_SYMBOLS = {"meta": "⌘", "cmd": "⌘", "command": "⌘", "controlormeta": "⌘", "control": "⌃", "ctrl": "⌃",
               "alt": "⌥", "option": "⌥", "shift": "⇧", "enter": "↵", "escape": "esc", "tab": "⇥",
               "backspace": "⌫", "arrowup": "↑", "arrowdown": "↓", "arrowleft": "←", "arrowright": "→"}


def options(plan: dict) -> dict:
    found = {key: plan[key] for key in DICT_OPTIONS if isinstance(plan.get(key), dict)}
    found.update({key: plan[key] for key in LIST_OPTIONS if isinstance(plan.get(key), list)})
    found.update({key: plan[key] for key in TEXT_OPTIONS if isinstance(plan.get(key), str)})
    return found


def load(path: Path | None) -> tuple[list | None, dict]:
    if not path:
        return None, {}
    plan = json.loads(Path(path).read_text())
    if isinstance(plan, list):
        return plan, {}
    return plan.get("steps"), options(plan)


def keys_label(combo: str) -> str:
    parts = [p for p in combo.replace(" ", "").split("+") if p]
    return " ".join(KEY_SYMBOLS.get(p.lower(), p.upper() if len(p) == 1 else p) for p in parts)


def mark_highlight(step: dict, index: int, events: list, resolve, box_of) -> None:
    wanted = step.get("highlight")
    if not wanted:
        return
    if wanted is True:
        own = next((e for e in reversed(events) if e.get("step") == index and e.get("box")), None)
        if own:
            own["highlight"], own["highlight_lead"] = own["box"], True
            return
    target = step.get("target") if wanted is True else wanted
    locator, _ = resolve(target)
    if locator is None or locator.count() == 0:
        return
    box = box_of(locator.first)
    if not box:
        return
    for event in reversed(events):
        if event.get("step") == index:
            event["highlight"] = box
            return


def annotate(events: list, steps: list) -> None:
    for event in events:
        step = steps[event["step"]] if "step" in event and event["step"] < len(steps) else None
        if not isinstance(step, dict):
            continue
        for note in STEP_NOTES:
            if step.get(note):
                event["effects" if note == "effect" else note] = step[note]
