"""Bias engine golden fixtures + missing/stale semantics (REQ-3, REQ-11, REQ-13)."""
import pytest

from app.engine.bias import compute_bias, label_for


def seed_world(store, now_days_ago=1):
    """Deterministic fixture world: rising gold, falling real yields, fresh COT."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 20, tzinfo=timezone.utc)
    for i in range(30):
        d = (base - timedelta(days=29 - i)).strftime("%Y-%m-%d")
        avail = (base - timedelta(days=29 - i)).replace(hour=23).isoformat()
        store.upsert_bars("GC=F", [{"date": d, "open": 4000 + i * 5, "high": 4010 + i * 5,
                                    "low": 3990 + i * 5, "close": 4005 + i * 5,
                                    "volume": 1000 + i * 10,
                                    "available_at": avail}], "yahoo")
        store.upsert_macro("DFII10", [{"date": d, "value": 2.5 - i * 0.01,
                                       "available_at": avail}], "fred")
        store.upsert_macro("DGS10", [{"date": d, "value": 4.3 - i * 0.005,
                                      "available_at": avail}], "fred")
        store.upsert_macro("DTWEXBGS", [{"date": d, "value": 104.0 - i * 0.05,
                                         "available_at": avail}], "fred")
    store.upsert_cot([
        {"as_of": f"2026-10-{d:02d}", "available_at": f"2026-10-{d + 3:02d}T00:00:00+00:00",
         "mm_long": 150000 + i * 4000, "mm_short": 62000 - i * 500,
         "open_interest": 395000 + i * 1000}
        for i, d in enumerate((6, 13, 20, 27, 30))
    ] + [{"as_of": "2026-11-17", "available_at": "2026-11-20T00:00:00+00:00",
          "mm_long": 200000, "mm_short": 50000, "open_interest": 405000}], "cftc")
    store.upsert_options([{"as_of": "2026-11-20", "available_at": "2026-11-20T12:00:00+00:00",
                           "atm_iv": 19.0, "rr25": 1.5, "expected_range_low": 3900,
                           "expected_range_high": 4120, "oi_call": None, "oi_put": None}], "tv")
    store.upsert_manual("etf", "etf_flows", [
        {"date": "2026-11-18", "value": 3.0}, {"date": "2026-11-19", "value": 4.0},
        {"date": "2026-11-20", "value": 2.5}])


def test_golden_fixture_full_world(store, cfg):
    seed_world(store)
    b = compute_bias(store, "2026-11-21T00:00:00+00:00", cfg, now="2026-11-21T06:00:00+00:00")
    # strong bullish fixture: uptrend + falling yields + rising COT + positive RR + ETF inflow
    assert b["score"] is not None
    assert b["score"] > 20
    assert b["label"] in {"Bullish", "Strong bullish"}
    assert b["reliability"] > 0.5
    assert set(b["dimensions_used"]) == {"structure", "options", "macro", "cot", "etf"}
    assert b["data_freshness"]["yahoo"]["status"] == "ok"
    assert -100 <= b["score"] <= 100


def test_stale_data_reduces_reliability(store, cfg):
    seed_world(store)
    fresh = compute_bias(store, "2026-11-21T00:00:00+00:00", cfg,
                         now="2026-11-21T06:00:00+00:00")
    # same data but "now" is 30 days later -> everything stale
    old = compute_bias(store, "2026-11-21T00:00:00+00:00", cfg,
                       now="2026-12-21T06:00:00+00:00")
    assert old["reliability"] < fresh["reliability"]
    assert any(v["status"] in ("stale", "missing") for v in old["data_freshness"].values())


def test_missing_dimension_renormalizes_and_floor_suppresses(store, cfg, tmp_path):
    from app.store import Store as S

    bare = S(tmp_path / "bare.db")
    # truly empty world: no data at all
    empty = compute_bias(bare, "2026-11-21T00:00:00+00:00", cfg,
                         now="2026-11-21T06:00:00+00:00")
    assert empty["score"] is None
    assert empty["label"] == "insufficient data — no directional call"
    # only macro data present -> renormalized aggregate over 1 dimension
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 20, tzinfo=timezone.utc)
    for i in range(10):
        d = (base - timedelta(days=9 - i)).strftime("%Y-%m-%d")
        avail = d + "T23:00:00+00:00"
        bare.upsert_macro("DFII10", [{"date": d, "value": 2.5 - i * 0.02,
                                      "available_at": avail}], "fred")
    only_macro = compute_bias(bare, "2026-11-21T00:00:00+00:00", cfg,
                              now="2026-11-21T06:00:00+00:00")
    assert only_macro["dimensions_used"] == ["macro"]
    # score equals the single dimension score scaled to -100..100
    s = only_macro["dimensions"]["macro"]["score"]
    assert only_macro["score"] == pytest.approx(s * 100, abs=0.5)
    # SPEC §5 / D4 (all-dims weighted mean): macro alone is 20% of the evidence
    # -> reliability 0.2 < floor 0.5 -> headline is suppressed, not a silent call
    assert only_macro["reliability"] == pytest.approx(0.2, abs=0.01)
    assert only_macro["label"] == "insufficient data — no directional call"


def test_low_reliability_suppresses_headline_label(store, cfg):
    seed_world(store)
    b = compute_bias(store, "2026-11-21T00:00:00+00:00", cfg,
                     now="2027-01-20T06:00:00+00:00")  # everything ancient
    if b["reliability"] < cfg["thresholds"]["reliability_floor"]:
        assert b["label"].startswith("insufficient data")


def test_label_thresholds():
    c = {"thresholds": {"strong_bull": 60, "bull": 20, "bear": -20, "strong_bear": -60}}
    assert label_for(70, c) == "Strong bullish"
    assert label_for(60, c) == "Strong bullish"
    assert label_for(20, c) == "Bullish"
    assert label_for(19.9, c) == "Neutral"
    assert label_for(-20, c) == "Bearish"
    assert label_for(-60, c) == "Strong bearish"
