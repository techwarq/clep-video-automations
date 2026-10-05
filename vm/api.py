"""Talks back to the Worker API: job status, finished video, drafts."""
from pathlib import Path

import httpx

import config

HEADERS = {"Authorization": f"Bearer {config.INTERNAL_KEY}"}
BASE = f"{config.API_URL}/internal"


def update(job_id: str, status: str, **fields) -> None:
    httpx.patch(f"{BASE}/jobs/{job_id}", headers=HEADERS, json={"status": status, **fields}).raise_for_status()


def put_video(job_id: str, mp4: Path) -> str:
    # sent whole (not chunked) so R2 gets a Content-Length; Workers cap request bodies at 100 MB
    r = httpx.put(f"{BASE}/jobs/{job_id}/video", headers=HEADERS, content=mp4.read_bytes(), timeout=600)
    r.raise_for_status()
    return r.json()["video_id"]


def put_draft(job_id: str, data: bytes) -> None:
    httpx.put(f"{BASE}/jobs/{job_id}/draft", headers=HEADERS, content=data, timeout=120).raise_for_status()


def get_draft(key: str) -> bytes:
    r = httpx.get(f"{BASE}/drafts/{key}", headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.content
