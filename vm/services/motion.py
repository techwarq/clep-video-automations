"""Launch-film engine (engines/motion = allore-pipelines/pipeline_motion)."""
import io
import shutil
import tarfile
from pathlib import Path
from typing import Optional, Tuple

import config
from services import run_engine

ENGINE = config.ENGINES / "motion"


def _film(job_id: str) -> Path:
    return ENGINE / "projects" / job_id / "film3" / "agent" / "film"


def run(job_id: str, input: dict, draft: Optional[bytes] = None) -> Tuple[Path, float]:
    """Full run (site → agent → render), or with a draft: restore the saved film and only render it ($0 model)."""
    if draft:
        with tarfile.open(fileobj=io.BytesIO(draft), mode="r:gz") as tar:
            tar.extractall(_film(job_id).parent)
        cmd = [config.MOTION_PYTHON, "motion.py", "render", job_id, "--workers", config.RENDER_WORKERS]
    else:
        cmd = [config.MOTION_PYTHON, "motion.py", "film", job_id, "--url", input["url"],
               "--request", input.get("request", ""), "--seconds", str(input.get("seconds", 36)),
               "--workers", config.RENDER_WORKERS, "--budget", config.MOTION_BUDGET_USD, "--yes"]
    spend = run_engine(cmd, ENGINE)
    return ENGINE / "projects" / job_id / "renders" / f"agent_{job_id}.mp4", spend


def draft(job_id: str) -> Optional[bytes]:
    """The film the agent wrote (html, plan, mix, fonts, marks) as tar.gz, or None if it never got that far."""
    film = _film(job_id)
    if not (film / "index.html").exists():
        return None
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(film, arcname="film")
    return buf.getvalue()


def cleanup(job_id: str) -> None:
    # drop the heavy parts (frames, local mp4); the draft is in R2, the rest stays for debugging
    pr = ENGINE / "projects" / job_id
    for d in (pr / "film3" / "agent" / "frames", pr / "film3" / "agent_dry" / "frames", pr / "renders"):
        shutil.rmtree(d, ignore_errors=True)
