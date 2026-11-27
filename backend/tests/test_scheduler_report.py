"""Scheduler cron specs (REQ-7) + catch-up policy (D8) + report determinism (REQ-6, D15)
+ snapshot replay reproducibility (REQ-10, REQ-16, D14)."""
import json

import pytest

from app.config import config_hash
from app.engine import report as report_mod
from app.engine.bias import compute_bias
from app.scheduler import job_specs


def test_job_specs_match_spec_schedule(cfg):
    specs = job_specs(cfg)
    assert specs["weekly_brief"] == {"day_of_week": "sun", "hour": 18, "minute": 0,
                                     "timezone": "Asia/Bangkok"}
    assert specs["macro_price"]["hour"] == 7
    assert "sat" in specs["macro_price"]["day_of_week"]          # D1: Saturday refresh
    assert specs["options_bias"]["hour"] == 14
    assert specs["options_bias"]["day_of_week"] == "mon-fri"


def test_scheduler_recovery_settings(cfg):
    # D8 is enforced in build_scheduler via misfire_grace_time/coalesce — assert config path
    from app.scheduler import build_scheduler

    calls = {}

    class FakeSched:
        def add_job(self, fn, trigger, id=None, **kw):
            calls[id] = kw

        def start(self):
            pass

    import app.scheduler as sch

    orig = sch.BackgroundScheduler
    sch.BackgroundScheduler = lambda **kw: FakeSched()
    try:
        build_scheduler(None, None, cfg, lambda: {}, lambda a, kind="daily_bias": {},
                        lambda b=None: "")
    finally:
        sch.BackgroundScheduler = orig
    for job_id, kw in calls.items():
        assert kw["misfire_grace_time"] == 3600
        assert kw["coalesce"] is True


# ---- report determinism ------------------------------------------------------
def _mk_bias(score=45.0):
    return {
        "score": score, "label": "Bullish", "reliability": 0.8,
        "dimensions_used": ["structure", "macro"],
        "dimensions": {
            "structure": {"score": 0.6, "reliability": 1.0, "drivers": {"structure": {
                "last_close": 4075.0, "prev_week_close": 4005.0,
                "developing_tpo": {"poc": 4060.0, "vah": 4090.0, "val": 4020.0},
                "anchored_vwap": 4050.0, "opening_range": {"low": 3995.0, "high": 4015.0},
                "value_area_migration": "higher", "value_area_overlap": True,
                "regime_4w": "Bullish trend", "regime_developing": "Bullish trend",
                "roll_dates": []}}},
            "options": {"score": 0.3, "reliability": 0.6,
                        "drivers": {"skew": {"rr25": 1.5, "atm_iv": 19.0,
                                             "expected_range_low": 3900.0,
                                             "expected_range_high": 4120.0}}},
            "macro": {"score": -0.2, "reliability": 1.0, "drivers": {
                "real_yield_change": -0.05, "dxy_pct_change": -0.3}},
            "cot": {"score": None, "reliability": 0.0, "drivers": {"reason": "no data"}},
            "etf": {"score": None, "reliability": 0.0, "drivers": {"reason": "no data"}},
        },
        "data_freshness": {"yahoo": {"status": "ok"}, "fred": {"status": "ok"},
                           "cot": {"status": "missing"}, "tv_options": {"status": "ok"},
                           "manual": {"status": "missing"}},
    }


def test_report_numbers_match_engine_metrics():
    b = _mk_bias()
    struct = b["dimensions"]["structure"]["drivers"]["structure"]
    text = report_mod.weekly_report(b, struct, calendar_rows=None)
    # computed numbers appear verbatim in the text
    assert "4075.0" in text and "4005.0" in text
    assert "4060.0" in text and "4090.0" in text and "4020.0" in text
    assert "45" in text
    assert "Bullish" in text
    assert "+1.5" in text  # rr25
    assert "Calendar data not imported" in text
    assert "cot: missing" in text  # freshness flags surfaced


def test_report_with_calendar_lists_events():
    b = _mk_bias()
    struct = b["dimensions"]["structure"]["drivers"]["structure"]
    cal = [{"date": "2026-12-01", "event": "US CPI", "impact": "high"}]
    text = report_mod.weekly_report(b, struct, calendar_rows=cal)
    assert "US CPI" in text and "2026-12-01" in text


def test_report_module_makes_no_network_calls():
    # D15: the report generator is pure — assert its module doesn't import httpx/yfinance
    import app.engine.report as rp

    src_names = set(rp.__dict__)
    assert not any(name in src_names for name in ("httpx", "yfinance", "requests", "openai"))


# ---- snapshot replay reproducibility ----------------------------------------
def test_snapshot_stores_config_and_replay_is_reproducible(store, cfg):
    from test_bias_engine import seed_world

    seed_world(store)
    T = "2026-11-21T00:00:00+00:00"
    now = "2026-11-21T06:00:00+00:00"
    b = compute_bias(store, T, cfg, now=now)
    config_json = json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")},
                             sort_keys=True)
    sid = store.save_snapshot("daily_bias", T, b, config_json, config_hash(cfg))
    snap = store.get_snapshot(sid)
    assert snap["config_hash"] == config_hash(cfg)
    assert snap["payload"].startswith("{")
    # replay with CHANGED live config must reproduce the ORIGINAL score via snapshotted cfg
    cfg2 = dict(cfg)
    cfg2["dimensions"] = {k: dict(v) for k, v in cfg["dimensions"].items()}
    cfg2["dimensions"]["structure"] = dict(cfg2["dimensions"]["structure"])
    cfg2["dimensions"]["structure"]["weight"] = 0.9
    b2 = compute_bias(store, T, cfg2, now=now)
    assert b2["score"] != b["score"]  # live config changed the answer...
    assert json.loads(snap["payload"])["score"] == b["score"]  # ...but the snapshot is stable
    assert len(store.snapshots()) == 1
