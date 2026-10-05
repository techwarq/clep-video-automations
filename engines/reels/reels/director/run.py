"""prompt -> finished reel. The whole automatic path in one place:

    plan -> voice -> Pinterest assets -> write comp.html -> check/repair -> visual review -> render
"""

from __future__ import annotations

import time
from pathlib import Path

from reels import config, llm
from reels.assets import media, picker, voice
from reels.director import compose
from reels.director import plan as planner
from reels.project import Project
from reels.render import capture


def confirm_paid(what: str, usd: float, yes: bool) -> bool:
    """Every paid generation call goes through here first."""
    print(f"[cost] {what}: about ${usd:.2f}")
    if yes:
        return True
    try:
        return input("Proceed with this paid call? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def narrate(project: Project, plan: dict, voice_file: Path | None, tts: str | None, yes: bool) -> None:
    text = planner.script(plan)
    if plan["narration"] == "none" or not text:
        project.write("words.json", [])
        (project.root / "voice.wav").unlink(missing_ok=True)
    elif voice_file:
        voice.from_audio(project, voice_file, script=text)
    elif tts and confirm_paid(f"ElevenLabs voice '{tts}', {len(text)} chars", voice.estimate(text), yes):
        voice.tts(project, text, voice=tts)
    else:
        print("[voice] no voice source — silent draft timed at reading speed (add --tts or --voice-file)")
        voice.placeholder(project, text)


def make(prompt: str, style: str | None = None, video: Path | None = None, voice_file: Path | None = None,
         tts: str | None = None, seconds: int | None = None, model: str | None = None, yes: bool = False,
         vision: bool = True, review: bool = True, out: Path | None = None, workers: int = 4) -> Path:
    t0 = time.time()
    project = Project.new(prompt[:40])
    project.install_runtime()
    print(f"[reels] project {project.root}")

    transcript = None
    if video:                                    # talking head: the speaker's video and words come first
        style = "talking_head"
        media.add(project, "face", video, max_seconds=None, note="the speaker (voice.wav is its audio)")
        transcript = voice.from_audio(project, video)

    plan = planner.make(prompt, style=style, seconds=seconds, transcript=transcript, model=model)
    project.write("plan.json", plan)
    if not video:
        narrate(project, plan, voice_file, tts, yes)
    if plan["assets"]:
        picker.gather(project, plan["assets"], vision=vision, model=model)

    compose.write(project, plan, model)
    left = compose.repair(project, plan, model)
    if review and not left:
        compose.review(project, plan, model)
    if compose.problems(project):
        raise RuntimeError(f"composition still fails the checks — edit {project.html} and run "
                           f"`python -m reels render {project.root.name}`")
    result = capture.render(project, out=out, workers=workers)
    print(f"[reels] done in {time.time() - t0:.0f}s · {llm.LEDGER['calls']} model calls · "
          f"${llm.LEDGER['usd']:.3f} → {result}")
    return result


def resolve(name: str) -> Project:
    p = Path(name)
    root = p if p.is_dir() else config.PROJECTS_DIR / name
    if not root.is_dir():
        raise SystemExit(f"no project {name!r} (looked in {config.PROJECTS_DIR})")
    return Project(root)
