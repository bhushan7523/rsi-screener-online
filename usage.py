"""Counts API calls per data source per day and remembers any limit a source reports."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

FILE = Path(__file__).resolve().parent / ".cache" / "usage.json"

# Known daily limits when a source doesn't report one itself (None = no daily limit).
DEFAULT_LIMITS = {"yahoo": None, "angel": None, "tapetide": None}
# Sources whose limit depends on your plan and isn't known until the source reports it.
PLAN_BASED = {"tapetide"}


def _load() -> dict:
    try:
        return json.loads(FILE.read_text())
    except (OSError, ValueError):
        return {}


def record(source: str, calls: int = 1, limit: int | None = None,
           remaining: int | None = None, resets: str | None = None) -> None:
    data = _load()
    today = date.today().isoformat()
    s = data.setdefault(source, {})
    if s.get("date") != today:
        s.clear()
        s["date"] = today
    s["calls"] = s.get("calls", 0) + calls
    if limit is not None:
        s["limit"] = limit
    if remaining is not None:
        s["remaining"] = remaining
    if resets:
        s["resets"] = resets
    FILE.parent.mkdir(exist_ok=True)
    FILE.write_text(json.dumps(data, indent=1))


def summary(source: str) -> dict:
    s = _load().get(source, {})
    today = date.today().isoformat()
    calls = s.get("calls", 0) if s.get("date") == today else 0
    limit = s.get("limit", DEFAULT_LIMITS.get(source)) if s.get("date") == today else DEFAULT_LIMITS.get(source)
    remaining = s.get("remaining") if s.get("date") == today else None
    if remaining is None and limit is not None:
        remaining = max(limit - calls, 0)
    plural = "s" if calls != 1 else ""
    if limit is None and remaining is None and source in PLAN_BASED:
        text = f"Limit set by your plan · {calls} call{plural} today"
    elif limit is None and remaining is None:
        text = f"No daily limit · {calls} call{plural} today"
    else:
        text = f"{remaining} of {limit} left today" if limit is not None else f"{remaining} left today"
    resets = s.get("resets") if s.get("date") == today else None
    return {"calls": calls, "limit": limit, "remaining": remaining, "resets": resets, "text": text,
            "plan_based": source in PLAN_BASED and limit is None and remaining is None}
