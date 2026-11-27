"""Collector primitives: typed rows, explicit failures, freshness math (D9)."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable


class CollectorError(RuntimeError):
    """Raised when a collector cannot produce usable data — never silently empty."""


def days_since(iso_ts: str, now: "datetime | str | None" = None) -> float:
    dt = datetime.fromisoformat(iso_ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now is None:
        now_dt = datetime.now(timezone.utc)
    elif isinstance(now, str):
        now_dt = datetime.fromisoformat(now)
    else:
        now_dt = now
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=timezone.utc)
    return (now_dt - dt).total_seconds() / 86400.0


def freshness(source: str, last_as_of: str | None, staleness_days: dict,
              now: "datetime | str | None" = None) -> dict:
    """ok/stale/missing per source; limits come from config staleness_days (D7)."""
    if not last_as_of:
        return {"source": source, "status": "missing", "as_of": None, "age_days": None}
    age = days_since(last_as_of, now)
    limit = float(staleness_days.get(source, 7))
    status = "ok" if age <= limit else "stale"
    return {"source": source, "status": status, "as_of": last_as_of, "age_days": round(age, 2),
            "limit_days": limit}


def squash(x: float | None, scale: float, invert: bool = False) -> float | None:
    """Bounded signal mapping to [-1, 1]: score = tanh(x/scale), optionally inverted."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    v = math.tanh(float(x) / scale)
    return -v if invert else v


def combine(scores: list[tuple[float, float]]) -> float:
    """Weighted mean of (score, weight) pairs; weights renormalized (D3/D4)."""
    total_w = sum(w for _, w in scores)
    if total_w <= 0 or not scores:
        return 0.0
    return sum(s * w for s, w in scores) / total_w


def retry(call: Callable[[], Any], attempts: int = 3, backoff: float = 1.0,
          sleep: Callable[[float], None] | None = None) -> Any:
    """Bounded retry with linear backoff (D17)."""
    import time

    sleeper = sleep or time.sleep
    last: Exception | None = None
    for i in range(attempts):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 — collector boundary
            last = exc
            if i < attempts - 1:
                sleeper(backoff * (i + 1))
    raise CollectorError(f"all {attempts} attempts failed: {last}")


def next_weekday(d: date, add_days: int) -> date:
    return d + timedelta(days=add_days)
