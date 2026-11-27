"""No look-ahead (REQ-8, D5): engines at time T must not see future rows even
if the DB contains them; publication lag (available_at) respected."""
import pytest


def seed(store):
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 20, tzinfo=timezone.utc)
    for i in range(20):
        d = (base - timedelta(days=19 - i)).strftime("%Y-%m-%d")
        avail = (base - timedelta(days=19 - i)).replace(hour=23).isoformat()
        store.upsert_bars("GC=F", [{"date": d, "open": 4000 + i * 5, "high": 4015 + i * 5,
                                    "low": 3995 + i * 5, "close": 4005 + i * 5,
                                    "volume": 1000, "available_at": avail}], "yahoo")
    # COT rows: 4 older weeks (published well before T) + the 2026-11-17 report
    # observed 2026-11-17 but ONLY published 2026-11-20 (3-day lag)
    rows = [{"as_of": f"2026-10-{d:02d}", "available_at": f"2026-10-{d + 3:02d}T00:00:00+00:00",
             "mm_long": 150000 + i * 5000, "mm_short": 60000, "open_interest": 390000}
            for i, d in enumerate((13, 20, 27, 30))]
    rows.append({"as_of": "2026-11-17", "available_at": "2026-11-20T00:00:00+00:00",
                 "mm_long": 200000, "mm_short": 50000, "open_interest": 405000})
    store.upsert_cot(rows, "cftc")
    # a FUTURE bar (2026-11-25) already stored (out-of-order collection happens)
    store.upsert_bars("GC=F", [{"date": "2026-11-25", "open": 4200, "high": 4300,
                                "low": 4100, "close": 4290, "volume": 1000,
                                "available_at": "2026-11-25T23:59:00+00:00"}], "yahoo")


def test_future_bars_do_not_leak(store, cfg):
    seed(store)
    from app.engine.bias import compute_bias
    from app.engine.structure import weekly_structure

    T = "2026-11-21T00:00:00+00:00"
    b_before = compute_bias(store, T, cfg, now=T)
    # add more future data, recompute at the same T
    store.upsert_bars("GC=F", [{"date": "2026-11-26", "open": 4300, "high": 4400,
                                "low": 4200, "close": 4390, "volume": 1000,
                                "available_at": "2026-11-26T23:59:00+00:00"}], "yahoo")
    b_after = compute_bias(store, T, cfg, now=T)
    assert b_before["score"] == b_after["score"]
    assert b_before["dimensions"] == b_after["dimensions"]
    # structure directly: no bar dated > T can enter
    bars = store.bars("GC=F", T, limit=120)
    assert all(r["date"] <= T[:10] for r in bars)
    assert len(bars) == 20


def test_publication_lag_respected(store, cfg):
    seed(store)
    from app.engine.bias import compute_bias

    # at T = 2026-11-18 the 2026-11-17 COT is NOT yet published (avail 11-20)
    T = "2026-11-18T06:00:00+00:00"
    b = compute_bias(store, T, cfg, now=T)
    cot_dim = b["dimensions"]["cot"]
    assert cot_dim["score"] is None  # only the unpublished 11-17 report is new at T;
    # store.cot at T excludes it (available_at > T) -> 4 usable rows < 5 min history
    # at T = 2026-11-21 it is published and used
    b2 = compute_bias(store, "2026-11-21T06:00:00+00:00", cfg,
                      now="2026-11-21T06:00:00+00:00")
    assert b2["dimensions"]["cot"]["score"] is not None
