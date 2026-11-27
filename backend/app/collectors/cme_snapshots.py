"""CME snapshot puller: JSON files committed to the data branch by the GitHub
Actions browser collector (DECISIONS.md). NEVER scrapes CME from the VPS.

Snapshot file format (committed by the workflow as snapshots/YYYY-MM-DD.json):
{
  "snapshot_date": "2026-11-27",
  "tenor": "GC1!",
  "source": "real" | "mock",
  "oi_by_strike": [{"strike": 4000, "call_oi": 123, "put_oi": 45}, ...],
  "vol2vol": {"atm_iv": 18.2, "rr25": 1.4, "expected_range": {"low": 3900, "high": 4120}}
}

Provenance (D2): rows stored as source 'cme-real' or 'cme-mock'; production
config cme.accept_mock=false excludes mock rows everywhere.
"""
from __future__ import annotations

import json

import httpx

from .base import CollectorError

SNAPSHOT_PATH = "snapshots/{date}.json"
REQUIRED_KEYS = {"snapshot_date", "tenor", "source", "oi_by_strike"}


def validate_snapshot(payload: dict) -> None:
    missing = REQUIRED_KEYS - set(payload)
    if missing:
        raise CollectorError(f"cme snapshot missing keys: {sorted(missing)}")
    if payload["source"] not in ("real", "mock"):
        raise CollectorError(f"cme snapshot bad provenance: {payload['source']!r}")
    if not isinstance(payload["oi_by_strike"], list):
        raise CollectorError("cme snapshot oi_by_strike must be a list")


def latest_snapshot_dates(client: httpx.Client, base_url: str, token: str,
                          days: int = 14) -> list[str]:
    """Probe the last `days` dates for existing snapshot files (no directory listing on raw)."""
    from datetime import date, timedelta

    today = date.today()
    found: list[str] = []
    for i in range(days):
        d = (today - timedelta(days=i)).isoformat()
        url = f"{base_url}/{SNAPSHOT_PATH.format(date=d)}"
        try:
            resp = client.get(url, headers=_headers(token))
            if resp.status_code == 200:
                found.append(d)
        except httpx.HTTPError:
            continue
    return found


def _headers(token: str) -> dict:
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"token {token}"
    return h


def fetch(base_url: str, token: str = "", client: httpx.Client | None = None,
          probe_days: int = 14) -> list[dict]:
    """Pull all snapshot files found in the probe window. Token REQUIRED for
    private data branches (D10) — an unauthenticated pull of a private repo
    404s and surfaces as CollectorError after probing."""
    own = client is None
    client = client or httpx.Client(timeout=30)
    try:
        dates = latest_snapshot_dates(client, base_url, token, days=probe_days)
        if not dates:
            raise CollectorError("cme_snapshots: no snapshot files found in probe window")
        out = []
        for d in dates:
            url = f"{base_url}/{SNAPSHOT_PATH.format(date=d)}"
            resp = client.get(url, headers=_headers(token))
            resp.raise_for_status()
            payload = json.loads(resp.text)
            validate_snapshot(payload)
            out.append(payload)
        return out
    except CollectorError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CollectorError(f"cme_snapshots pull failed: {exc}") from exc
    finally:
        if own:
            client.close()


def store_snapshots(store, payloads: list[dict]) -> int:
    """Store with provenance mapping (D2): source -> 'cme-real' | 'cme-mock'."""
    from .base import CollectorError

    n = 0
    for p in payloads:
        validate_snapshot(p)
        tag = "cme-real" if p["source"] == "real" else "cme-mock"
        # publication-aware availability: snapshot dated D is known end of D (D5)
        avail = p["snapshot_date"] + "T23:59:00+00:00"
        store.upsert_cme_snapshot(p["snapshot_date"], p["tenor"], p, tag, avail)
        n += 1
    return n
