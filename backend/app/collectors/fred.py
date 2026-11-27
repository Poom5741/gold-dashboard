"""FRED daily series collector — CSV endpoint, no API key (verified 27 Nov 2026).

Series: DFII10 (10Y real yield), DGS10 (10Y nominal), DTWEXBGS (broad dollar
index; 'DXY10Y' does not exist on FRED — live-verified substitution, D18).

Publication lag: FRED daily series publish ~1 day after the value date, so
available_at = value_date + 1 day (D5).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from .base import CollectorError

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
SERIES = ("DFII10", "DGS10", "DTWEXBGS")


def _parse_csv(text: str, series: str) -> list[dict]:
    rows: list[dict] = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2 or "observation_date" not in lines[0]:
        raise CollectorError(f"fred: unexpected CSV shape for {series}")
    for ln in lines[1:]:
        parts = ln.split(",")
        if len(parts) < 2 or parts[0].startswith("<"):
            continue
        value = parts[1].strip()
        if value in ("", ".", "NA"):
            continue
        rows.append({"date": parts[0], "value": float(value)})
    if not rows:
        raise CollectorError(f"fred: no usable observations for {series}")
    return rows


def _available_at(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    return d.isoformat()


def fetch(series: str, client: httpx.Client | None = None, last_n: int = 10) -> list[dict]:
    own = client is None
    client = client or httpx.Client(timeout=30)
    try:
        resp = client.get(FRED_CSV.format(series=series))
        resp.raise_for_status()
        rows = _parse_csv(resp.text, series)
    except CollectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CollectorError(f"fred fetch failed for {series}: {exc}") from exc
    finally:
        if own:
            client.close()
    rows = rows[-last_n:]
    for r in rows:
        r["available_at"] = _available_at(r["date"])
    return rows


def fetch_all(client: httpx.Client | None = None) -> dict[str, list[dict]]:
    return {s: fetch(s, client=client) for s in SERIES}
