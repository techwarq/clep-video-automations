"""OpenRouter chat calls with a cost ledger and a hard budget.

Default model is Muse Spark 1.3 (cheap, takes images and video). Any OpenRouter
model id works via REELS_MODEL or --model; the skills carry the craft, not the model.
"""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from reels import config

# $ per million tokens (in, out) when OpenRouter does not report the cost itself.
PRICE = {
    "meta/muse-spark-1.3": (1.25, 4.25),
    "meta/muse-spark-1.3-contributor": (0.10, 0.20),
    "anthropic/claude-sonnet-5.5": (2.0, 10.0),
    "anthropic/claude-opus-5.5": (4.0, 20.0),
}
LEDGER = {"calls": 0, "in": 0, "out": 0, "usd": 0.0}


class BudgetExceeded(RuntimeError):
    pass


def _post(payload: dict, timeout: int = 600) -> dict:
    req = urllib.request.Request(
        config.OPENROUTER_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                 "Content-Type": "application/json", "X-Title": "allore reels"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _cost(model: str, usage: dict) -> float:
    if usage.get("cost") is not None:
        return float(usage["cost"])
    pi, po = PRICE.get(model, (3.0, 15.0))
    return (usage.get("prompt_tokens", 0) * pi + usage.get("completion_tokens", 0) * po) / 1e6


def _reasoning(model: str) -> dict:
    # Muse Spark refuses reasoning=off; the skills already carry the thinking, so keep it low everywhere.
    return {"effort": "low"}


def chat(messages: list[dict], model: str | None = None, max_tokens: int = 16000,
         temperature: float = 0.6, tag: str = "call") -> str:
    """One completion. Retries transient failures; raises BudgetExceeded past REELS_BUDGET_USD."""
    model = model or config.MODEL
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set (pipeline/.env)")
    if LEDGER["usd"] >= config.BUDGET_USD:
        raise BudgetExceeded(f"budget reached (${LEDGER['usd']:.3f} of ${config.BUDGET_USD:.2f}); "
                             "raise REELS_BUDGET_USD to continue")
    err: Exception | None = None
    for attempt in range(4):
        try:
            r = _post({"model": model, "messages": messages, "max_tokens": max_tokens,
                       "temperature": temperature, "reasoning": _reasoning(model),
                       "usage": {"include": True}})
            if "error" in r:
                raise RuntimeError(str(r["error"])[:300])
            u = r.get("usage") or {}
            c = _cost(model, u)
            LEDGER["calls"] += 1
            LEDGER["in"] += u.get("prompt_tokens", 0)
            LEDGER["out"] += u.get("completion_tokens", 0)
            LEDGER["usd"] += c
            out = (r["choices"][0]["message"].get("content") or "").strip()
            print(f"[llm] {tag}: {u.get('prompt_tokens', 0)}→{u.get('completion_tokens', 0)} tok "
                  f"· ${c:.4f} · total ${LEDGER['usd']:.3f}", flush=True)
            if out:
                return out
            err = RuntimeError("empty response")
        except urllib.error.HTTPError as e:
            err = RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}")
            if 400 <= e.code < 500 and e.code != 429:   # bad request / auth: retrying won't help
                raise err
        except Exception as e:  # network hiccups, malformed replies
            err = e
        print(f"[llm] retry {attempt + 1}: {err}", flush=True)
        time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"model call failed: {err}")


def extract_json(text: str):
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.S)
    raw = fenced.group(1) if fenced else re.search(r"(\{.*\}|\[.*\])", text, re.S).group(1)
    return json.loads(raw)


def chat_json(messages: list[dict], tag: str = "json", **kw):
    msgs = list(messages)
    for _ in range(3):
        out = chat(msgs, tag=tag, **kw)
        try:
            return extract_json(out)
        except Exception as e:
            msgs = msgs + [{"role": "assistant", "content": out[:20000]},
                           {"role": "user", "content": f"That was not valid JSON ({e}). "
                                                       "Reply with ONLY the corrected JSON."}]
    raise RuntimeError(f"[{tag}] model did not return valid JSON")


FENCE = re.compile(r"```html\s*\n(.*?)\n```", re.S)


def extract_html(text: str) -> str:
    m = FENCE.search(text)
    if m:
        return m.group(1).strip()
    m = re.search(r"(<!doctype html.*</html>)", text, re.S | re.I)
    if not m:
        raise ValueError("reply has no ```html block")
    return m.group(1).strip()


def image_part(path: Path) -> dict:
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


def text_part(s: str) -> dict:
    return {"type": "text", "text": s}
