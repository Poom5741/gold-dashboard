"""CFTC Disaggregated COT collector — dataset 72hh-3qpy, gold code 088691.

Dataset correction (live-verified 27 Nov 2026 via publicreporting.cftc.gov
/api/views): 6dca-aqww is *Legacy* Futures-Only and has NO managed-money
fields; the Disaggregated Futures-Only report (which carries managed money
positions, SPEC §4.4) is 72hh-3qpy with `m_money_positions_long_all` /
`m_money_positions_short_all`. Filter field keeps the full `cftc_` prefix.
Release schedule: positions as of Tuesday, released Friday ~15:30 ET
(~Saturday 03:30 Bangkok) — so available_at = position date + 3 days
(D5, conservative).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from .base import CollectorError

SODA_URL = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json"
CONTRACT_CODE = "088691"


def _available_at(as_of: str) -> str:
    d = datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=3)
    return d.isoformat()


def fetch(client: httpx.Client | None = None, limit: int = 30) -> list[dict]:
    params = {
        "$select": "report_date_as_yyyy_mm_dd,cftc_contract_market_code,"
                   "m_money_positions_long_all,m_money_positions_short_all,"
                   "open_interest_all",
        "cftc_contract_market_code": CONTRACT_CODE,
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": str(limit),
    }
    own = client is None
    client = client or httpx.Client(timeout=30)
    try:
        resp = client.get(SODA_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        raise CollectorError(f"cftc fetch failed: {exc}") from exc
    finally:
        if own:
            client.close()
    rows: list[dict] = []
    for r in data:
        mm_long = r.get("m_money_positions_long_all")
        mm_short = r.get("m_money_positions_short_all")
        if mm_long is None or mm_short is None:
            continue
        raw_date = r["report_date_as_yyyy_mm_dd"][:10]
        rows.append({
            "as_of": raw_date,
            "available_at": _available_at(raw_date),
            "mm_long": float(mm_long),
            "mm_short": float(mm_short),
            "open_interest": float(r.get("open_interest_all") or 0) or None,
        })
    if not rows:
        raise CollectorError("cftc: no usable COT rows")
    return rows
