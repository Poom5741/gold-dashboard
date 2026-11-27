"""Yahoo Finance daily bars collector: GC=F (gold futures), DX-Y.NYB (dollar index).

available_at = session close: bar dated D is known after D 23:59 UTC for GC=F
(COMEX settles ~19:30 UTC; conservative full-day boundary keeps completed-bars
guarantee simple) — actually we use next-day 00:00 UTC boundary only for today's
bar exclusion; historical bars get available_at = D 23:59 UTC (D5/D12).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import CollectorError


def _norm(df: Any) -> list[dict]:
    rows: list[dict] = []
    for idx, r in df.iterrows():
        o, h, l, c = (r.get("Open"), r.get("High"), r.get("Low"), r.get("Close"))
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (o, h, l, c)):
            continue
        rows.append({
            "date": idx.strftime("%Y-%m-%d"),
            "open": float(o), "high": float(h), "low": float(l), "close": float(c),
            "volume": float(r["Volume"]) if r.get("Volume") not in (None, 0) else None,
        })
    if not rows:
        raise CollectorError("yahoo returned no usable bars")
    return rows


def _available_at(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return (d + timedelta(hours=23, minutes=59)).isoformat()


def fetch(symbol: str = "GC=F", period: str = "120d", fetcher=None) -> list[dict]:
    """fetcher: injected yfinance-like (tests); default lazily imports yfinance."""
    if fetcher is None:
        import yfinance  # deferred: heavy import, and tests inject a stub

        def fetcher(ticker: str, period: str):  # noqa: E306
            return yfinance.Ticker(ticker).history(period=period)

    try:
        df = fetcher(symbol, period)
    except Exception as exc:  # noqa: BLE001
        raise CollectorError(f"yahoo fetch failed for {symbol}: {exc}") from exc
    rows = _norm(df)
    for r in rows:
        r["available_at"] = _available_at(r["date"])
    return rows
