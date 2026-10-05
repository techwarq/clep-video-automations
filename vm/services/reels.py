"""Reels engine (engines/reels = allore-pipelines/pipeline)."""
import shutil
from pathlib import Path
from typing import Optional, Tuple

import config
from services import run_engine

ENGINE = config.ENGINES / "reels"


def run(job_id: str, input: dict, draft: Optional[bytes] = None) -> Tuple[Path, float]:
    # reels keeps no draft yet: a retry runs the whole reel again
    out = ENGINE / "output" / f"{job_id}.mp4"
    cmd = [config.REELS_PYTHON, "-m", "reels", "make", input["prompt"], "--out", str(out),
           "--workers", config.RENDER_WORKERS, "--yes"]
    if input.get("style"):
        cmd += ["--style", input["style"]]
    if input.get("tts"):
        cmd += ["--tts", input["tts"]]
    return out, run_engine(cmd, ENGINE)


def draft(job_id: str) -> Optional[bytes]:
    return None


def cleanup(job_id: str) -> None:
    # one job at a time on the VM, so the whole scratch space belongs to this job
    for d in ("projects", "output"):
        shutil.rmtree(ENGINE / d, ignore_errors=True)
