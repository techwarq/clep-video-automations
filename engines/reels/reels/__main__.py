"""reels CLI. Run from pipeline/:  venv/bin/python -m reels <command> ...

    make "prompt" [--style S] [--video F] [--voice-file F] [--tts VOICE] [--yes]   prompt -> finished reel
    new NAME [--style S]            empty project for hand-written comp.html
    search NAME "query" [--images]  Pinterest contact sheet into the project
    pick NAME KEY SHEET.json INDEX  download one pin from a sheet as media KEY
    add NAME KEY FILE [--start S]   add a local video/image as media KEY
    voice NAME --draft | --file F | --tts VOICE [--yes]
    brief NAME                      timing + media summary (what comp.html should be written against)
    check NAME                      lint + smoke test + stills contact sheet
    render NAME [--out F]           comp.html -> output/NAME.mp4
    skills [FILE]                   list skill files, or print one
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reels import config, skills
from reels.director import run


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="reels", description="Prompt -> vertical reel via an HTML composition.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("make", help="prompt -> finished reel (model-directed)")
    m.add_argument("prompt")
    m.add_argument("--style", choices=list(skills.STYLES))
    m.add_argument("--video", type=Path, help="talking-head source video")
    m.add_argument("--voice-file", type=Path, help="your own voiceover recording")
    m.add_argument("--tts", metavar="VOICE", help="ElevenLabs voice (lily, matilda, liam, brian, ...) — paid")
    m.add_argument("--yes", action="store_true", help="skip the paid-call confirmation")
    m.add_argument("--seconds", type=int)
    m.add_argument("--model", help=f"OpenRouter model id (default {config.MODEL})")
    m.add_argument("--no-vision", action="store_true", help="skip the vision screen on Pinterest picks")
    m.add_argument("--no-review", action="store_true", help="skip the visual review pass")
    m.add_argument("--out", type=Path)
    m.add_argument("--workers", type=int, default=4)

    n = sub.add_parser("new")
    n.add_argument("name")
    n.add_argument("--style", choices=list(skills.STYLES), default="pinterest_edit")
    s = sub.add_parser("search")
    s.add_argument("name")
    s.add_argument("query")
    s.add_argument("--images", action="store_true")
    p = sub.add_parser("pick")
    p.add_argument("name")
    p.add_argument("key")
    p.add_argument("sheet", type=Path)
    p.add_argument("index", type=int)
    a = sub.add_parser("add")
    a.add_argument("name")
    a.add_argument("key")
    a.add_argument("file", type=Path)
    a.add_argument("--start", type=float, default=0.0)
    a.add_argument("--full", action="store_true", help="keep the whole clip (talking heads)")
    v = sub.add_parser("voice")
    v.add_argument("name")
    g = v.add_mutually_exclusive_group(required=True)
    g.add_argument("--draft", action="store_true")
    g.add_argument("--file", type=Path)
    g.add_argument("--tts", metavar="VOICE")
    v.add_argument("--yes", action="store_true")
    for cmd in ("brief", "check"):
        sub.add_parser(cmd).add_argument("name")
    r = sub.add_parser("render")
    r.add_argument("name")
    r.add_argument("--out", type=Path)
    r.add_argument("--workers", type=int, default=4)
    k = sub.add_parser("skills")
    k.add_argument("file", nargs="?")
    return ap


def main() -> None:
    a = _parser().parse_args()
    if a.cmd == "make":
        run.make(a.prompt, style=a.style, video=a.video, voice_file=a.voice_file, tts=a.tts, seconds=a.seconds,
                 model=a.model, yes=a.yes, vision=not a.no_vision, review=not a.no_review, out=a.out,
                 workers=a.workers)
    elif a.cmd == "new":
        _new(a.name, a.style)
    elif a.cmd == "skills":
        print(skills.read(a.file) if a.file and a.file.endswith(".md") else
              skills.example(a.file) if a.file else skills.listing())
    else:
        _project_cmd(a, run.resolve(a.name))


def _new(name: str, style: str) -> None:
    from reels.project import Project, slug
    project = Project(config.PROJECTS_DIR / slug(name))
    project.install_runtime()
    if not project.plan:
        project.write("plan.json", {"title": name, "style": style, "narration": "voice", "music": "warm_indie",
                                    "beats": [{"id": "b1", "text": "", "visual": ""}], "assets": [],
                                    "look": "", "content": {}, "tail": 0.8})
    project.write("words.json", project.words)
    project.write("media.json", project.media)
    print(f"[reels] {project.root}\n  next: edit plan.json, add media, `voice`, write comp.html "
          f"(skills/engine.md + skills/{skills.STYLES[style][0]}), then `check` and `render`")


def _project_cmd(a, project) -> None:
    from reels.assets import media, picker, voice
    from reels.render import capture, check
    if a.cmd == "search":
        picker.sheet(a.query, project.root / "sheets", images=a.images)
    elif a.cmd == "pick":
        picker.pick(project, a.key, a.sheet, a.index)
    elif a.cmd == "add":
        media.add(project, a.key, a.file, start=a.start, max_seconds=None if a.full else media.MAX_SECONDS)
    elif a.cmd == "voice":
        text = " ".join(b.get("text", "") for b in project.plan.get("beats", [])).strip()
        if a.file:
            voice.from_audio(project, a.file, script=text or None)
        elif a.tts:
            if run.confirm_paid(f"ElevenLabs voice '{a.tts}', {len(text)} chars", voice.estimate(text), a.yes):
                voice.tts(project, text, voice=a.tts)
        else:
            voice.placeholder(project, text)
    elif a.cmd == "brief":
        print(project.summary())
    elif a.cmd == "check":
        reel = project.write_data()
        found = check.lint(project.html.read_text(), project.media) or check.smoke(project.html, reel["dur"])
        print("problems:\n" + "\n".join(f"- {p}" for p in found) if found else "checks pass")
        from reels.director.compose import review_times
        files = check.stills(project.html, review_times(project), project.root / "stills")
        print(f"stills: {check.contact_sheet(files, project.root / 'stills' / 'sheet.jpg')}")
    elif a.cmd == "render":
        capture.render(project, out=a.out, workers=a.workers)
    print(json.dumps({"project": str(project.root)}))


if __name__ == "__main__":
    main()
