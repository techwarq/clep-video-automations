"""Record on this machine, edit and render on Clep: the local half of a clip (reaches localhost and logged-in pages).

    # feature demo of an instrumented [data-clep="ai-research"]
    python record.py --url http://localhost:3000 --name ai-research --query "AI agents" --out clip.mp4
    # walkthrough, no instrumentation
    python record.py --url http://localhost:3000 --sections "hero, pricing" --duration 10 --out tour.mp4
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

import feature_recorder
import page_scan
import tour_recorder
import clip_plan
import hosted_api
import screencast
import tour_plan

CAPTURES = Path.home() / ".clep" / "captures"
EDIT_OPTIONS = ("style", "aspect", "duration", "fps", "quality", "movement", "size", "bg")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "clip"


def record_capture(args: argparse.Namespace, capture_dir: Path) -> None:
    if args.name:
        steps, plan_options = clip_plan.load(args.steps_file)
        feature_recorder.record(args.url, args.name, capture_dir, query=args.query, steps=steps, plan_options=plan_options,
                     capture_scale=screencast.scale_for(args.quality))
        return
    sections = [s.strip() for s in args.sections.split(",")] if args.sections else []
    _, plan_options = clip_plan.load(args.steps_file)
    page = page_scan.scan_content(args.url)
    stops = tour_plan.ground_sections(sections, page.get("sections") or [])
    tour_recorder.record_tour(args.url, capture_dir, sections=stops or None,
                      per_section=tour_plan.section_hold(args.duration, max(len(stops), 1)),
                      capture_scale=screencast.scale_for(args.quality), private=plan_options.get("private"))


def clip_options(args: argparse.Namespace, capture_id: str) -> dict:
    options = {"capture": capture_id, "url": args.url, "name": args.name or f"tour-{_slug(args.url)}"}
    options.update({k: getattr(args, k) for k in EDIT_OPTIONS if getattr(args, k) is not None})
    if not args.captions:
        options["captions"] = False
    return options


def main(args: argparse.Namespace) -> Path:
    capture_dir = CAPTURES / f"{_slug(args.name or args.url)}-{int(time.time())}"
    try:
        record_capture(args, capture_dir)
        capture_id = hosted_api.upload_capture(capture_dir)
    finally:
        shutil.rmtree(capture_dir, ignore_errors=True)
    job_id = hosted_api.request_clip(clip_options(args, capture_id))
    hosted_api.wait_for(job_id)
    return hosted_api.download(job_id, args.out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Record a page locally; Clep edits and renders the clip.")
    ap.add_argument("--url", required=True)
    ap.add_argument("--name", default=None, help="data-clep feature to demo; omit for a walkthrough")
    ap.add_argument("--query", default=None, help="text to type (feature demo)")
    ap.add_argument("--steps-file", default=None, type=Path, help="multi-step plan JSON (feature demo)")
    ap.add_argument("--sections", default=None, help='walkthrough stops, e.g. "hero, pricing"')
    ap.add_argument("--out", default=Path("clep/clip.mp4"), type=Path)
    ap.add_argument("--style", default=None)
    ap.add_argument("--aspect", default=None)
    ap.add_argument("--duration", default=None, type=float)
    ap.add_argument("--fps", default=None, type=int)
    ap.add_argument("--quality", default=None)
    ap.add_argument("--movement", default=None)
    ap.add_argument("--size", default=None)
    ap.add_argument("--bg", default=None)
    ap.add_argument("--no-captions", dest="captions", action="store_false", default=True)
    try:
        print(f"[clep] clip ready: {main(ap.parse_args())}")
    except RuntimeError as e:
        print(f"[clep] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
