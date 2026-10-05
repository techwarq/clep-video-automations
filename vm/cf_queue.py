"""Cloudflare Queues HTTP pull consumer."""
import json

import httpx

import config

BASE = f"https://api.cloudflare.com/client/v4/accounts/{config.CF_ACCOUNT_ID}/queues/{config.CF_QUEUE_ID}/messages"
HEADERS = {"Authorization": f"Bearer {config.CF_API_TOKEN}"}


def pull() -> list[dict]:
    """One message at a time: the VM renders one video at a time."""
    r = httpx.post(f"{BASE}/pull", headers=HEADERS, json={"batch_size": 1, "visibility_timeout_ms": config.LEASE_MS})
    r.raise_for_status()
    msgs = r.json()["result"]["messages"]
    for m in msgs:
        if isinstance(m["body"], str):
            m["body"] = json.loads(m["body"])
    return msgs


def ack(lease_id: str) -> None:
    httpx.post(f"{BASE}/ack", headers=HEADERS, json={"acks": [{"lease_id": lease_id}]}).raise_for_status()
