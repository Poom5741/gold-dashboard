"""Options metrics collector via TVdataOptionOI (MIT, vendored dependency).

Per verified findings (research-sources.md): the chain provides real IV and
delta for COMEX:GC1! but open_interest is always None — so this collector
derives ATM IV, 25-delta risk reversal and the implied weekly expected range
ONLY (D3 sub-score 'skew'). OI positioning enters via manual import.

available_at = as_of + 1h (scanner data is effectively current when fetched).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .base import CollectorError

SYMBOL = "COMEX:GC1!"


def _nearest_dte(chain: list[dict], min_dte: int = 1) -> int | None:
    """Nearest expiry with usable rows; dte=0 (same-day) options are skipped —
    their IV is dominated by expiry noise, not the weekly signal."""
    dtes = [c["dte"] for c in chain
            if c.get("dte") is not None and c["dte"] >= min_dte
            and c.get("iv") is not None and c.get("delta") is not None]
    return min(dtes) if dtes else None


def _rr25(chain: list[dict]) -> float | None:
    """25-delta risk reversal = IV(call, 0.25d) - IV(put, -0.25d), nearest DTE."""
    best_dte = _nearest_dte(chain)
    if best_dte is None:
        return None
    call_iv = put_iv = None
    for c in chain:
        if c.get("dte") != best_dte or c.get("iv") is None or c.get("delta") is None:
            continue
        d = c["delta"]
        if 0.20 <= d <= 0.30 and (call_iv is None or abs(d - 0.25) < abs(call_iv[1] - 0.25)):
            call_iv = (c["iv"], d)
        if -0.30 <= d <= -0.20 and (put_iv is None or abs(d + 0.25) < abs(put_iv[1] + 0.25)):
            put_iv = (c["iv"], d)
    if call_iv is None or put_iv is None:
        return None
    return (call_iv[0] - put_iv[0]) * 100.0  # in vol points


def _atm_iv(chain: list[dict]) -> float | None:
    """ATM IV = IV of the option whose |delta| is closest to 0.5 at the
    nearest expiry (dte >= 1). ATM is ~50-delta, NOT the <=10-delta wing."""
    best_dte = _nearest_dte(chain)
    if best_dte is None:
        return None
    best = None
    for c in chain:
        if c.get("dte") != best_dte or c.get("iv") is None or c.get("delta") is None:
            continue
        d = abs(c["delta"])
        if 0.35 <= d <= 0.65 and (best is None or abs(d - 0.5) < abs(best[0] - 0.5)):
            best = (d, c["iv"])
    return (best[1] * 100.0) if best else None


def expected_weekly_range(spot: float | None, atm_iv_pct: float | None) -> tuple | None:
    """Implied 1-week range: spot * iv * sqrt(7/365), +- band."""
    if not spot or not atm_iv_pct or spot <= 0:
        return None
    move = spot * (atm_iv_pct / 100.0) * math.sqrt(7.0 / 365.0)
    return (spot - move, spot + move)


def fetch(spot: float | None, chain_fetcher=None, symbol: str = SYMBOL) -> list[dict]:
    try:
        chain: list[dict]
        if chain_fetcher is None:
            from tvdataoption import TVdataOption  # deferred import (MIT dependency)

            df = TVdataOption().get_option_chain(symbol)
            chain = df.to_dict("records")  # NaN sanitized below
            for c in chain:
                for k, v in c.items():
                    if isinstance(v, float) and math.isnan(v):
                        c[k] = None
        else:
            chain = chain_fetcher(symbol)
    except CollectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CollectorError(f"tvdataoption fetch failed: {exc}") from exc
    atm_iv = _atm_iv(chain)
    rr = _rr25(chain)
    lo, hi = expected_weekly_range(spot, atm_iv) or (None, None)
    if atm_iv is None and rr is None:
        raise CollectorError("tvdataoption: chain had no usable IV/delta rows")
    now = datetime.now(timezone.utc)
    return [{
        "as_of": now.strftime("%Y-%m-%d"),
        # D5: scanner data is known AT fetch time — no artificial +1h lag
        # (the +1h variant made every row invisible to the engine for an hour).
        "available_at": now.isoformat(),
        "atm_iv": atm_iv, "rr25": rr,
        "expected_range_low": lo, "expected_range_high": hi,
        "oi_call": None, "oi_put": None,   # TV has no GC options OI — manual import only
    }]
