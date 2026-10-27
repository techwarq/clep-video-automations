"""The hosted Clep API as seen from the user's machine: upload a capture, ask for the clip, wait, download it.

Stdlib only, so the local recorder needs nothing beyond Playwright.
Key from CLEP_API_KEY; CLEP_API_URL overrides the hosted address.
"""
from __future__ import annotations

import json
import os
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("CLEP_API_URL", "https://api.clep.abstraklabs.com").rstrip("/")
POLL_SECONDS = 10
WAIT_LIMIT_SECONDS = 30 * 60


class HostedError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("CLEP_API_KEY", "").strip()
    if not key:
        raise HostedError("CLEP_API_KEY is not set: create a key in the Clep dashboard and export it")
    return key


def _request(method: str, path: str, body: dict | bytes | None = None, timeout: int = 120) -> bytes:
    headers = {"X-API-Key": _api_key()}
    data = body
    if isinstance(body, dict):
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except ValueError:
            pass
        raise HostedError(f"{method} {path} → {e.code}: {detail}") from None


def _call(method: str, path: str, body: dict | bytes | None = None) -> dict:
    return json.loads(_request(method, path, body) or b"{}")


def _pack(capture_dir: Path, into: Path) -> None:
    with tarfile.open(into, "w") as tar:
        for name in ("trace.json", "frames.json", "frames"):
            tar.add(capture_dir / name, arcname=name)


def upload_capture(capture_dir: Path) -> str:
    """Send a recorded capture to Clep in fixed-size parts; returns its capture id."""
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "capture.tar"
        _pack(capture_dir, archive)
        total = archive.stat().st_size
        started = _call("POST", "/api/captures")
        capture_id, upload_id, part_size = started["capture_id"], started["upload_id"], started["part_size"]
        parts = []
        with archive.open("rb") as source:
            number = 1
            while chunk := source.read(part_size):
                print(f"[clep] uploading {min(number * part_size, total) / 1e6:.0f} / {total / 1e6:.0f} MB", flush=True)
                sent = json.loads(_request("PUT", f"/api/captures/{capture_id}/parts/{number}?upload={upload_id}",
                                           chunk, timeout=600))
                parts.append({"part": number, "etag": sent["etag"]})
                number += 1
        _call("POST", f"/api/captures/{capture_id}/complete", {"upload_id": upload_id, "parts": parts})
    return capture_id


def request_clip(options: dict) -> str:
    return _call("POST", "/api/clips", options)["job_id"]


def wait_for(job_id: str) -> dict:
    deadline = time.time() + WAIT_LIMIT_SECONDS
    last_status = None
    while time.time() < deadline:
        job = _call("GET", f"/api/jobs/{job_id}")
        if job["status"] != last_status:
            print(f"[clep] job {job_id}: {job['status']}", flush=True)
            last_status = job["status"]
        if job["status"] == "done":
            return job
        if job["status"] == "error":
            raise HostedError(job.get("error") or "the render failed")
        time.sleep(POLL_SECONDS)
    raise HostedError(f"job {job_id} is still running after {WAIT_LIMIT_SECONDS // 60} min; check it later with GET /api/jobs/{job_id}")


def download(job_id: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(_request("GET", f"/api/jobs/{job_id}/video", timeout=600))
    return out
