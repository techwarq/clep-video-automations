"""Google VM worker: pull a job → run its engine → upload → report. One job at a time.

    python main.py                                   # production: pull from the Cloudflare queue
    python main.py --job '{"id": ..., "engine": ..., "input": {...}}'   # local test: run one job, no queue
"""
import json
import sys
import time
import traceback

import api
import cf_queue
import config
from router import SERVICES


def handle(msg: dict) -> None:
    job = msg["body"]
    job_id, engine = job["id"], job["engine"]
    service = SERVICES[engine]
    draft = api.get_draft(job["draft_key"]) if job.get("draft_key") else None
    print(f"[{job_id}] {engine} start" + (" (re-render from draft)" if draft else ""), flush=True)
    api.update(job_id, "running")
    spend = 0.0
    try:
        mp4, spend = service.run(job_id, job["input"], draft)
        api.put_video(job_id, mp4)
        api.update(job_id, "done", cost_usd=spend)
        print(f"[{job_id}] done · ${spend:.3f}", flush=True)
    except Exception as e:
        traceback.print_exc()
        api.update(job_id, "failed", error=str(e)[:2000], cost_usd=getattr(e, "spend", spend))
    finally:
        try:
            if not draft and (d := service.draft(job_id)):   # keep what the model made, so a retry needn't pay again
                api.put_draft(job_id, d)
        except Exception:
            traceback.print_exc()
        service.cleanup(job_id)
    if "lease_id" in msg:
        cf_queue.ack(msg["lease_id"])  # retries go through the API (POST /v1/jobs/:id/retry)


def main() -> None:
    print(f"worker up" + (f" · exits after {config.IDLE_EXIT_MINUTES:g} idle min" if config.IDLE_EXIT_MINUTES else ""), flush=True)
    last_work = time.time()
    while True:
        try:
            msgs = cf_queue.pull()
        except Exception:
            traceback.print_exc()
            msgs = []
        for m in msgs:
            handle(m)
            last_work = time.time()
        if not msgs:
            if config.IDLE_EXIT_MINUTES and time.time() - last_work > config.IDLE_EXIT_MINUTES * 60:
                print("queue empty, idle limit reached: exiting so the VM can power off", flush=True)
                return                                   # exit code 0 = idle; deploy/startup.sh shuts the VM down
            time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--job"]:
        handle({"body": json.loads(sys.argv[2])})
    else:
        main()
