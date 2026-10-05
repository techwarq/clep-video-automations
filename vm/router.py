"""engine name → service. Each service has run(job_id, input) -> mp4 Path and cleanup(job_id)."""
from services import motion, reels

SERVICES = {
    "reels": reels,
    "motion": motion,
}
