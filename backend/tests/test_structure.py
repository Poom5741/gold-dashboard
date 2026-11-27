"""Structure engine tests — hand-computed fixtures (REQ-4), roll handling (REQ-14),
completed-bar exclusion (D12)."""
from app.engine import structure as st


def bars_from(closes, opens=None, vol=1000.0):
    rows = []
    for i, c in enumerate(closes):
        o = (opens[i] if opens else c - 5)
        rows.append({"date": f"2026-11-{10 + i:02d}", "open": float(o), "high": float(c) + 10,
                     "low": float(c) - 10, "close": float(c), "volume": vol})
    return rows


def test_profile_poc_vah_val_hand_computed():
    # dominant-volume bar at 4100: POC must land near 4100, VA around it
    bars = []
    vols = [100, 100, 100000, 100, 100]
    for i, (c, v) in enumerate(zip([4000, 4050, 4100, 4050, 4000], vols)):
        bars.append({"date": f"2026-11-{10 + i:02d}", "open": c - 5, "high": c + 10,
                     "low": c - 10, "close": c, "volume": v})
    p = st.profile(bars)
    assert 4090 < p["poc"] < 4110
    assert p["val"] <= p["poc"] <= p["vah"]
    assert p["val"] >= 4079 and p["vah"] <= 4121  # VA hugs the dominant bar


def test_directional_efficiency_and_realized_vol():
    straight = bars_from([4000, 4020, 4040, 4060, 4080])
    choppy = bars_from([4000, 4080, 3980, 4060, 4080])
    eff_straight = st.directional_efficiency(straight)
    eff_choppy = st.directional_efficiency(choppy)
    assert eff_straight == pytest.approx(1.0)
    assert eff_choppy < eff_straight
    rv = st.realized_vol(straight)
    assert 0 < rv < 5.0  # annualized sanity


import pytest  # noqa: E402


def test_roll_detection_and_back_adjust():
    # roll: new contract level jumps between close 4050 -> open 4180 (~3.2% gap)
    closes = [4000, 4020, 4040, 4050, 4180, 4195, 4200]
    opens = [3995, 4015, 4035, 4045, 4180, 4190, 4195]
    bars = bars_from(closes, opens)
    rolls = st.detect_rolls(bars, gap_pct=1.5)
    assert rolls == [4]
    adjusted, roll_dates = st.back_adjust(bars, gap_pct=1.5)
    assert roll_dates == [bars[4]["date"]]
    # phantom move eliminated: post-roll series spliced onto the pre-roll level
    move_adjusted = adjusted[4]["close"] - adjusted[3]["close"]
    move_raw = bars[4]["close"] - bars[3]["close"]
    assert abs(move_adjusted) < abs(move_raw)
    # the roll's open no longer gaps vs the adjusted prior close
    assert abs(adjusted[4]["open"] - adjusted[3]["close"]) < 1e-6


def test_weekly_structure_shape_and_regime():
    cfg_trendy = {
        "thresholds": {"reliability_floor": 0.5, "min_history_days": 20},
        "scaling": {"roll_gap_pct": 1.5, "trend_efficiency": 0.6, "trend_move_atr": 1.5,
                    "compression_range_atr": 1.0},
    }
    uptrend = []
    base = 4000
    closes = [base + i * 20 for i in range(12)]
    bars = bars_from(closes)
    s = st.weekly_structure(bars, cfg_trendy)
    assert s is not None
    assert s["developing_tpo"]["poc"] > 0
    assert s["regime_4w"] in {"Bullish trend", "Bearish trend", "Rotational", "Compression"}
    assert s["regime_4w"] == "Bullish trend"  # strong steady uptrend
    score = st.structure_score(s, cfg_trendy)
    assert score is not None and score > 0


def test_insufficient_history_returns_none():
    cfg = {"thresholds": {}, "scaling": {"roll_gap_pct": 1.5}}
    assert st.weekly_structure(bars_from([4000, 4010, 4020]), cfg) is None


def test_opening_range_and_vwap():
    bars = bars_from([4000, 4050, 4100])
    orr = st.opening_range(bars)
    assert orr["high"] == 4010 and orr["low"] == 3990
    vw = st.anchored_vwap(bars)
    assert 3990 < vw < 4110
