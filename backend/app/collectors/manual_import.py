"""Manual CSV import adapter: OI by strike, ETF flows, economic calendar (D13/D16).

Expected CSV shapes (header row required):
- kind='oi' (per strike rows): date,strike,call_oi,put_oi
- kind='etf' (per date rows):  date,series,tonnes
- kind='calendar':             date,time,event,impact   (value=0 placeholder)

Validation (D16): header check, ISO date check, numeric sanity; duplicates are
idempotent via upsert; provenance source='manual' is set by the store.
"""
from __future__ import annotations

import csv
import io
from datetime import date as _date

from ..store import utciso
from .base import CollectorError

HEADERS = {
    "oi": {"date", "strike"},
    "etf": {"date", "series", "tonnes"},
    "calendar": {"date", "event"},
}


def _check_date(value: str, line_no: int) -> str:
    try:
        return _date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise CollectorError(f"manual import line {line_no}: bad date {value!r}") from exc


def parse_csv(kind: str, text: str) -> list[dict]:
    if kind not in HEADERS:
        raise CollectorError(f"manual import: unknown kind {kind!r}")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CollectorError("manual import: empty CSV")
    missing = HEADERS[kind] - set(h.strip().lower() for h in reader.fieldnames)
    if missing:
        raise CollectorError(f"manual import {kind}: missing columns {sorted(missing)}")
    rows: list[dict] = []
    for i, r in enumerate(reader, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        d = _check_date(r.get("date", ""), i)
        if kind == "oi":
            rows.append({
                "date": d, "series": f"strike_{float(r['strike']):.0f}",
                "value": float(r.get("call_oi") or 0) - float(r.get("put_oi") or 0),
            })
        elif kind == "etf":
            tonnes = float(r.get("tonnes") or 0)
            if tonnes < -1e6 or tonnes > 1e6:
                raise CollectorError(f"manual import line {i}: implausible tonnes {tonnes}")
            rows.append({"date": d, "series": r.get("series", "etf_flows"), "value": tonnes})
        else:  # calendar
            rows.append({"date": d, "series": "calendar", "value": 0.0,
                         "event": r.get("event", ""), "impact": r.get("impact", "unknown")})
    if not rows:
        raise CollectorError("manual import: no data rows")
    return rows


def import_text(store, kind: str, text: str) -> int:
    """Parse + idempotent store. Calendar rows also go to series 'calendar'."""
    rows = parse_csv(kind, text)
    if kind == "calendar":
        # an imported event is known at import time, not at the event date
        # (otherwise future events are invisible to every as_of<=now query)
        for r in rows:
            r["available_at"] = utciso()
        return store.upsert_manual("calendar", "calendar", rows)
    series_set = {r["series"] for r in rows}
    n = 0
    for s in series_set:
        n += store.upsert_manual(kind, s, [r for r in rows if r["series"] == s])
    return n or store.upsert_manual(kind, rows[0]["series"], rows)
