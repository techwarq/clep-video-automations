#!/usr/bin/env python3
"""pipeline_motion — url + request → a one-take launch film, made by an agent that writes, checks, looks and patches.

    python3 motion.py film <name> --url https://… --request "…" [--seconds 36]
                            [--model anthropic/claude-opus-5.5] [--fix-model anthropic/claude-sonnet-5.5] [--budget 1.00] --yes
    python3 motion.py film <name> --url https://… --dry [--no-render]      # whole loop offline, scripted model, $0

Nothing paid is generated (music + SFX come from film3/library). The only spend is the model, capped by --budget.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def cmd_film(a):
    # model settings are read by film3.llm at import time
    if a.dry:
        a.model, a.fix_model, a.yes = "dry", None, True        # scripted offline run of the whole loop: $0
    if a.model:
        os.environ["FILM3_MODEL"] = a.model
    if a.fix_model:
        os.environ["FILM3_FIX_MODEL"] = a.fix_model
    if a.budget is not None:
        os.environ["FILM3_BUDGET_USD"] = str(a.budget)
    from film3 import agent, llm
    if not a.yes:
        print(f"film agent: {llm.MODEL}{' (fixes on ' + a.fix_model + ')' if a.fix_model else ''} writes the whole film with tools.\n"
              f"Hard model budget ${llm.BUDGET:.2f}; every call counts in full, including stopped ones. No media generation.\n"
              "Re-run with --yes to proceed.")
        return
    print(agent.run(a.name, a.url, a.request or "", seconds=a.seconds, workers=a.workers, render_film=not a.no_render))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("film", help="url + request → launch film (agent mode)")
    p.add_argument("name"); p.add_argument("--url", required=True); p.add_argument("--request", default="")
    p.add_argument("--seconds", type=float, default=36)
    p.add_argument("--model", help="agent model (default: FILM3_MODEL or Muse Spark)")
    p.add_argument("--fix-model", help="cheaper model for the fix rounds after the film is written")
    p.add_argument("--budget", type=float, help="hard model budget in USD (default 1.00)")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--yes", action="store_true", help="confirm the model spend")
    p.add_argument("--dry", action="store_true", help="test the whole loop offline with a scripted model ($0; needs cached brand UI)")
    p.add_argument("--no-render", action="store_true", help="stop after the agent (no frames, no encode)")
    p.set_defaults(fn=cmd_film)
    r = sub.add_parser("render", help="re-render a film the agent already wrote (no model calls)")
    r.add_argument("name"); r.add_argument("--workers", type=int, default=6)
    r.set_defaults(fn=lambda a: print(__import__("film3.agent", fromlist=["rerender"]).rerender(a.name, a.workers)))
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
