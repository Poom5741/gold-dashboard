"""Refresh orchestration: fan-in collector execution with per-source isolation (D9).

A failing collector marks that source missing for this run; the refresh
continues for every other source. Only an all-failures run fails the job.
"""
from __future__ import annotations

import httpx

from .collectors import cftc, cme_snapshots, fred, tvdataoption, yahoo
from .collectors.base import CollectorError
from .config import Settings, load_config
from .store import Store


def run_refresh(store: Store, settings: Settings, now=None) -> dict:
    """Run all in-process collectors; returns per-source status report."""
    results: dict[str, dict] = {}
    cfg = load_config()

    # Yahoo price bars (GC=F and DXY proxy DX-Y.NYB)
    for symbol in ("GC=F", "DX-Y.NYB"):
        try:
            rows = yahoo.fetch(symbol)
            store.upsert_bars(symbol, rows, "yahoo")
            results[symbol] = {"status": "ok", "rows": len(rows)}
        except CollectorError as exc:
            results[symbol] = {"status": "failed", "error": str(exc)}

    # FRED series
    try:
        series_rows = fred.fetch_all()
        for name, srows in series_rows.items():
            store.upsert_macro(name, srows, "fred")
        results["fred"] = {"status": "ok", "rows": sum(len(v) for v in series_rows.values())}
    except CollectorError as exc:
        results["fred"] = {"status": "failed", "error": str(exc)}

    # CFTC COT
    try:
        rows = cftc.fetch()
        store.upsert_cot(rows, "cftc")
        results["cftc"] = {"status": "ok", "rows": len(rows)}
    except CollectorError as exc:
        results["cftc"] = {"status": "failed", "error": str(exc)}

    # Options skew via TVdataOptionOI (needs spot from stored bars)
    try:
        bars = store.bars("GC=F", _as_of(now), limit=1)
        spot = bars[-1]["close"] if bars else None
        rows = tvdataoption.fetch(spot)
        store.upsert_options(rows, "tv")
        results["tv_options"] = {"status": "ok", "rows": len(rows)}
    except CollectorError as exc:
        results["tv_options"] = {"status": "failed", "error": str(exc)}

    # CME snapshots from the data branch (skipped silently-missing in dev; reported)
    if settings.github_data_token:
        try:
            payloads = cme_snapshots.fetch(settings.cme_raw_base, settings.github_data_token)
            results["cme_snapshots"] = {"status": "ok",
                                        "stored": cme_snapshots.store_snapshots(store, payloads)}
        except CollectorError as exc:
            results["cme_snapshots"] = {"status": "failed", "error": str(exc)}
    else:
        results["cme_snapshots"] = {"status": "skipped",
                                    "reason": "GITHUB_DATA_TOKEN not configured (D10)"}

    results["all_failed"] = all(
        v.get("status") == "failed" for k, v in results.items()
        if k not in ("all_failed", "cme_snapshots")
    )
    return results


def _as_of(now=None) -> str:
    from .store import utciso
    return now if isinstance(now, str) else (now.isoformat() if now else utciso())
