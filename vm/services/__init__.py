"""Shared by the engine services: run an engine CLI, stream its log, and keep its model spend."""
import re
import subprocess
from pathlib import Path

# motion: "model spend $0.083", "[llm] … total $0.054" · reels: "12 model calls · $0.031 →"
SPEND = re.compile(r"(?:model spend|total|model calls ·) \$([0-9]+\.[0-9]+)")


class EngineError(RuntimeError):
    def __init__(self, msg: str, spend: float):
        super().__init__(msg)
        self.spend = spend


def run_engine(cmd: list, cwd: Path) -> float:
    """Run an engine to completion. Returns its model spend; on failure raises EngineError carrying the spend so far."""
    spend, tail = 0.0, []
    with subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as p:
        for line in p.stdout:
            print(line, end="", flush=True)
            tail = (tail + [line.rstrip()])[-15:]
            for m in SPEND.finditer(line):
                spend = max(spend, float(m.group(1)))
    if p.returncode:
        raise EngineError(f"engine exited {p.returncode}: " + " | ".join(l for l in tail if l)[-1500:], spend)
    return spend
