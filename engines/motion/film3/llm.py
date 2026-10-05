"""Model calls for film3 with a cost ledger and a hard budget. Default model: Muse Spark 1.3."""
from __future__ import annotations

import os
import re
import time
from typing import Dict, List

from director import llm as base

MODEL = os.environ.get("FILM3_MODEL", "meta/muse-spark-1.3-contributor")
PRICE, BUDGET, LEDGER = base.PRICE, base.BUDGET, base.LEDGER   # one ledger + hard cap shared with director/ calls
BudgetExceeded = base.BudgetExceeded
image_part = base.image_part


def _post(payload: dict, timeout: int = 900) -> dict:
    import json as _j, urllib.request
    key = os.environ.get("OPENROUTER_API_KEY")
    req = urllib.request.Request(base.BASE_URL.rstrip("/") + "/chat/completions", data=_j.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "pipeline_motion film3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _j.loads(r.read())


def text(messages: List[dict], max_tokens: int = 24000, temperature: float = 0.6, model: str = None, tag: str = "") -> str:
    model = model or MODEL
    if model == "dry":
        raise RuntimeError("dry mode makes no model calls (this step needs a cached result, e.g. brand UI in state.json)")
    err = None
    for attempt in range(4):
        base.guard(model, messages, max(max_tokens, 32000) if model.startswith("anthropic/") else max_tokens)
        try:
            payload = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "usage": {"include": True}}
            if model.startswith("anthropic/"):
                payload["reasoning"] = {"effort": "low"}            # the skills carry the thinking; spend tokens on the answer
                payload["max_tokens"] = max(max_tokens, 32000)
            r = _post(payload)
            if "error" in r:
                raise RuntimeError(str(r["error"])[:300])
            u = r.get("usage") or {}
            c = base.charge(model, u)
            ch = r["choices"][0]; out = (ch["message"].get("content") or "").strip()
            print(f"[llm] {tag or 'call'}: {u.get('prompt_tokens', 0)}→{u.get('completion_tokens', 0)} tok · ${c:.4f} · total ${LEDGER['usd']:.3f}", flush=True)
            if out:
                return out
            if ch.get("finish_reason") == "length":
                max_tokens = min(64000, max_tokens * 2)
            err = RuntimeError("empty response")
        except Exception as e:
            err = e
            body = getattr(e, "read", None)
            if body:
                try:
                    err = RuntimeError(f"{e}: {body().decode()[:300]}")
                except Exception:
                    pass
        print(f"[llm] retry {attempt + 1}: {err}", flush=True)
        time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"model call failed: {err}")


def json_(messages: List[dict], tag: str = "", **kw):
    msgs = list(messages)
    for attempt in range(3):
        out = text(msgs, tag=tag, **kw)
        try:
            return base.extract_json(out)
        except Exception as e:
            msgs = msgs + [{"role": "assistant", "content": out[:20000]},
                           {"role": "user", "content": f"That was not valid JSON ({e}). Reply with ONLY the corrected JSON object."}]
    raise RuntimeError("model did not return valid JSON")


FENCE = re.compile(r"```[a-zA-Z]*[ \t]+([\w.\-/]+)[ \t]*\n(.*?)\n```", re.S)


def files(reply: str) -> Dict[str, str]:
    """```lang name.ext … ``` blocks → {name: body}"""
    return {name.split("/")[-1]: body for name, body in FENCE.findall(reply)}


def chat_tools(messages: List[dict], tools: List[dict], tag: str = "", model: str = None, max_tokens: int = 32000) -> dict:
    """One agent turn with tool calling. Returns {"message": assistant message dict}. Counts cost (cache-aware via usage.cost)."""
    model = model or MODEL
    if model == "dry":                                          # scripted, offline, $0 (film3/dry.py)
        from . import dry
        LEDGER["calls"] += 1
        return dry.turn(messages, tools)
    err = None
    for attempt in range(4):
        base.guard(model, messages, max_tokens, tools)
        try:
            payload = {"model": model, "messages": messages, "tools": tools, "max_tokens": max_tokens, "usage": {"include": True}}
            if model.startswith("anthropic/"):
                payload["reasoning"] = {"effort": os.environ.get("FILM3_EFFORT", "low")}
            r = _post(payload)
            if "error" in r:
                raise RuntimeError(str(r["error"])[:400])
            u = r.get("usage") or {}
            c = base.charge(model, u)
            cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            print(f"[llm] {tag}: {u.get('prompt_tokens', 0)} in ({cached} cached) → {u.get('completion_tokens', 0)} out · ${c:.4f} · total ${LEDGER['usd']:.3f}", flush=True)
            return {"message": r["choices"][0]["message"]}
        except Exception as e:
            err = e
            body = getattr(e, "read", None)
            if body:
                try:
                    err = RuntimeError(f"{e}: {body().decode()[:400]}")
                except Exception:
                    pass
            print(f"[llm] retry {attempt + 1}: {err}", flush=True)
            time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"agent call failed: {err}")
