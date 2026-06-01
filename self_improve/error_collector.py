"""
Zbiera błędy/niepowodzenia z runów agenta do lokalnej bazy JSONL.

Użycie:
    from self_improve.error_collector import log_error
    log_error("scraper", "ValueError: ...", context={"url": "..."})
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

ERRORS_FILE = Path(__file__).parent / "errors.jsonl"


def log_error(component: str, error: str, context: Optional[dict] = None,
              tool_call: Optional[dict] = None, stack: Optional[str] = None) -> None:
    entry = {
        "ts": datetime.now().isoformat(),
        "component": component,
        "error": error,
        "context": context or {},
        "tool_call": tool_call,
        "stack": (stack or "")[:2000],
    }
    with ERRORS_FILE.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def list_errors(limit: int = 50) -> list[dict]:
    if not ERRORS_FILE.exists():
        return []
    out = []
    for line in ERRORS_FILE.read_text().splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out[-limit:]


def clear_errors():
    if ERRORS_FILE.exists():
        ERRORS_FILE.unlink()
