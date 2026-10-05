"""One LLM call helper: chat → JSON, with vision, via OpenRouter (OpenAI-compatible).

MOTION_DIRECTOR_MODEL picks the model (default meta/muse-spark-1.3-contributor;
the skill files + code-side guards carry the quality, not the model).
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from pathlib import Path
from typing import List, Optional

from . import paths  # noqa: F401  (loads .env)

MODEL = os.environ.get("MOTION_DIRECTOR_MODEL", "meta/muse-spark-1.3-contributor")
BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# One ledger + hard budget for every model call in a run (site intel, brand UI, agent turns).
PRICE = {"meta/muse-spark-1.3": (1.25, 4.25), "meta/muse-spark-1.3-contributor": (0.10, 0.20), "anthropic/claude-sonnet-5.5": (2.0, 10.0), "anthropic/claude-opus-5.5": (4.0, 20.0)}  # $ per M tokens (in, out)
BUDGET = float(os.environ.get("FILM3_BUDGET_USD", "1.00"))
LEDGER = {"calls": 0, "in": 0, "out": 0, "usd": 0.0}
IMAGE_TOKENS = 2000  # generous per-image allowance for the estimate


class BudgetExceeded(RuntimeError):
    pass


def estimate(model: str, messages: list, max_tokens: int, tools: Optional[list] = None) -> float:
    """Worst-case cost of one call: every input token uncached + the full max_tokens of output."""
    chars, images = 0, 0
    for m in messages:
        c = m.get("content")
        for part in (c if isinstance(c, list) else [{"type": "text", "text": c or ""}]):
            if part.get("type") == "image_url":
                images += 1
            else:
                chars += len(part.get("text") or "")
        chars += len(json.dumps(m.get("tool_calls") or ""))
    chars += len(json.dumps(tools or ""))
    pi, po = PRICE.get(model, (3.0, 15.0))
    return ((chars / 3 + images * IMAGE_TOKENS) * pi + max_tokens * po) / 1e6


def guard(model: str, messages: list, max_tokens: int, tools: Optional[list] = None) -> None:
    """Refuse a call before it is sent if its worst case would cross the budget."""
    est = estimate(model, messages, max_tokens, tools)
    if LEDGER["usd"] + est > BUDGET:
        raise BudgetExceeded(f"budget: ${LEDGER['usd']:.3f} spent + up to ${est:.3f} for this call > ${BUDGET:.2f} cap")


def charge(model: str, usage: dict) -> float:
    """Record a finished call; OpenRouter's own usage.cost wins over the price table."""
    if usage.get("cost") is not None:
        c = float(usage["cost"])
    else:
        pi, po = PRICE.get(model, (3.0, 15.0))
        c = (usage.get("prompt_tokens", 0) * pi + usage.get("completion_tokens", 0) * po) / 1e6
    LEDGER["calls"] += 1; LEDGER["in"] += usage.get("prompt_tokens", 0); LEDGER["out"] += usage.get("completion_tokens", 0)
    LEDGER["usd"] += c
    return c


def _post(payload: dict) -> dict:
    """Plain HTTPS to the OpenAI-compatible endpoint — no SDK, no version drift."""
    import urllib.request
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set (pipeline_motion/.env or pipeline/.env).")
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "X-Title": "pipeline_motion director"},
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def image_part(path: Path, max_w: int = 1280) -> dict:
    """Downscaled JPEG data-URL for a vision message."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)))
    # Very tall full-page shots: keep the top 2.2 screens, that's what the model needs.
    if im.height > im.width * 1.4:
        im = im.crop((0, 0, im.width, int(im.width * 1.4)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}


def extract_json(text: str):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=0)
    return json.loads(text[start:])


def chat(messages: List[dict], max_tokens: int = 16000, temperature: float = 0.8, model: Optional[str] = None) -> str:
    last_err = None
    model = model or MODEL
    for attempt in range(4):
        guard(model, messages, max_tokens)
        try:
            r = _post({"model": model, "messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature, "usage": {"include": True}})
            if "error" in r:
                raise RuntimeError(r["error"])
            c = charge(model, r.get("usage") or {})
            print(f"[llm] director: ${c:.4f} · total ${LEDGER['usd']:.3f}", flush=True)
            choice = r["choices"][0]
            text = (choice["message"].get("content") or "").strip()
            if text:
                return text
            if choice.get("finish_reason") == "length" and max_tokens < 32000:
                # Reasoning models can spend the whole budget thinking; give them room, no backoff.
                max_tokens = min(32000, max_tokens * 2)
                print(f"[llm] out of tokens while reasoning — retrying with max_tokens={max_tokens}")
                continue
            last_err = RuntimeError("empty response")
        except Exception as e:  # network / rate limit / provider error
            last_err = e
            body = getattr(e, "read", None)
            if body:
                try:
                    last_err = RuntimeError(f"{e}: {body().decode()[:500]}")
                except Exception:
                    pass
        print(f"[llm] retry {attempt + 1}: {last_err}")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM call failed after retries: {last_err}")


def chat_json(messages: List[dict], **kw):
    """chat() that insists on parseable JSON, feeding parse errors back once or twice."""
    msgs = list(messages)
    for attempt in range(3):
        text = chat(msgs, **kw)
        try:
            return extract_json(text)
        except Exception as e:
            msgs = msgs + [{"role": "assistant", "content": text},
                           {"role": "user", "content": f"That was not valid JSON ({e}). Reply with ONLY the JSON."}]
    raise RuntimeError("LLM never returned valid JSON")
