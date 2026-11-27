"""Market structure analytics from completed daily bars (SPEC §4.1–4.2).

All functions are pure and take rows with keys: date, open, high, low, close,
volume. Inputs must already be publication-aware filtered (store.bars does
as_of + available_at + completed-bar filtering — D5/D12).

Approximation disclosure (D11): TPO/POC/VAH/VAL built from daily bars use a
volume-proxy profile (typical price bucket weighting), NOT intraday TPO. The
UI/API must label these "daily-bar approximation".
"""
from __future__ import annotations

import math
from typing import Iterable


# ---- roll detection / back-adjustment (D6) ---------------------------------
def detect_rolls(bars: list[dict], gap_pct: float = 1.5) -> list[int]:
    """Return indices i where bar i opens with a suspected roll gap vs bar i-1."""
    rolls: list[int] = []
    for i in range(1, len(bars)):
        prev_close = bars[i - 1]["close"]
        if not prev_close:
            continue
        gap = abs(bars[i]["open"] / prev_close - 1.0) * 100.0
        if gap > gap_pct:
            rolls.append(i)
    return rolls


def back_adjust(bars: list[dict], gap_pct: float = 1.5) -> tuple[list[dict], list[str]]:
    """Difference-splice back-adjustment across detected roll boundaries.

    New-contract bars (roll index onward) are shifted down by the open gap so
    the spliced series is continuous: adjusted[roll].open == adjusted[roll-1].close.
    """
    rolls = detect_rolls(bars, gap_pct)
    if not rolls:
        return [dict(b) for b in bars], []
    adjusted = [dict(b) for b in bars]
    roll_dates: list[str] = []
    offset = 0.0
    roll_set = set(rolls)
    for i in range(len(adjusted)):
        if i in roll_set:
            gap = adjusted[i]["open"] - adjusted[i - 1]["close"]
            offset += gap
            roll_dates.append(adjusted[i]["date"])
        adjusted[i]["open"] -= offset
        adjusted[i]["high"] -= offset
        adjusted[i]["low"] -= offset
        adjusted[i]["close"] -= offset
    return adjusted, roll_dates


# ---- volume-proxy TPO / value area (D11) ------------------------------------
def profile(bars: Iterable[dict], bucket_count: int = 24) -> dict:
    """Volume-proxy price profile: distribute each bar's volume uniformly
    across buckets spanned by [low, high] at typical price weighting."""
    bars = list(bars)
    lo = min(b["low"] for b in bars)
    hi = max(b["high"] for b in bars)
    if hi <= lo:
        hi = lo + 1.0
    width = (hi - lo) / bucket_count
    hist = [0.0] * bucket_count
    for b in bars:
        typ = (b["high"] + b["low"] + b["close"]) / 3.0
        vol = b.get("volume") or 1.0
        start_bucket = max(0, min(bucket_count - 1, int((b["low"] - lo) / width)))
        end_bucket = max(0, min(bucket_count - 1, int((b["high"] - lo) / width)))
        span = end_bucket - start_bucket + 1
        for k in range(start_bucket, end_bucket + 1):
            hist[k] += vol / span
    poc_idx = max(range(bucket_count), key=lambda k: hist[k])
    poc = lo + (poc_idx + 0.5) * width
    total = sum(hist)
    # smallest POC-centered band covering ~70% of proxy volume (two-sided expansion)
    target = 0.70 * total
    acc = hist[poc_idx]
    low_i = high_i = poc_idx
    while acc < target and (low_i > 0 or high_i < bucket_count - 1):
        up = hist[high_i + 1] if high_i < bucket_count - 1 else -1.0
        down = hist[low_i - 1] if low_i > 0 else -1.0
        if up >= down:
            high_i += 1
            acc += up
        else:
            low_i -= 1
            acc += down
    vah = lo + (high_i + 1) * width
    val = lo + low_i * width
    return {"poc": poc, "vah": vah, "val": val, "hist": hist, "lo": lo, "width": width}


def tpo(bars: list[dict]) -> dict:
    """Developing/previous TPO set from a list of daily bars (per week)."""
    p = profile(bars)
    return {"poc": p["poc"], "vah": p["vah"], "val": p["val"],
            "approximation": "daily-bar volume-proxy profile (not intraday TPO)"}


def anchored_vwap(bars: list[dict]) -> float | None:
    num = den = 0.0
    for b in bars:
        typ = (b["high"] + b["low"] + b["close"]) / 3.0
        vol = b.get("volume") or 1.0
        num += typ * vol
        den += vol
    return num / den if den else None


def opening_range(week_bars: list[dict]) -> dict | None:
    if not week_bars:
        return None
    first = week_bars[0]
    return {"high": first["high"], "low": first["low"], "date": first["date"]}


def directional_efficiency(bars: list[dict]) -> float | None:
    """|net close move| / sum(|daily close moves|) in [0, 1]."""
    if len(bars) < 2:
        return None
    net = bars[-1]["close"] - bars[0]["close"]
    path = sum(abs(bars[i]["close"] - bars[i - 1]["close"]) for i in range(1, len(bars)))
    return abs(net) / path if path else None


def realized_vol(bars: list[dict], periods_per_year: int = 252) -> float | None:
    if len(bars) < 3:
        return None
    rets = [math.log(bars[i]["close"] / bars[i - 1]["close"])
            for i in range(1, len(bars)) if bars[i - 1]["close"] > 0 and bars[i]["close"] > 0]
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(periods_per_year)


def atr(bars: list[dict], period: int = 5) -> float | None:
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(len(bars) - period, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)


# ---- regime classification (§4.2) --------------------------------------------
def classify_regime(bars: list[dict], cfg: dict) -> dict | None:
    """Bullish trend / Bearish trend / Rotational / Compression."""
    if len(bars) < 6:
        return None
    a = atr(bars) or 1e-9
    net = bars[-1]["close"] - bars[0]["close"]
    eff = directional_efficiency(bars) or 0.0
    rng = max(b["high"] for b in bars) - min(b["low"] for b in bars)
    t = cfg["thresholds"]
    s = cfg["scaling"]
    if rng / a < s["compression_range_atr"]:
        regime = "Compression"
    elif eff >= s["trend_efficiency"] and abs(net) / a >= s["trend_move_atr"]:
        regime = "Bullish trend" if net > 0 else "Bearish trend"
    else:
        regime = "Rotational"
    return {"regime": regime, "net": net, "efficiency": round(eff, 3), "atr": a}


# ---- weekly aggregation (§4.1) ------------------------------------------------
def _week_bars(bars: list[dict], n: int = 5) -> list[dict]:
    return bars[-n:] if len(bars) >= n else bars


def weekly_structure(bars: list[dict], cfg: dict) -> dict | None:
    """Full weekly structure report from completed daily bars."""
    if len(bars) < 5:
        return None
    adjusted, roll_dates = back_adjust(bars, cfg["scaling"]["roll_gap_pct"])
    dev_bars = _week_bars(adjusted)
    prev_bars = _week_bars(adjusted[:-5]) if len(adjusted) >= 10 else []
    comp_bars = adjusted[-20:] if len(adjusted) >= 20 else adjusted
    dev = tpo(dev_bars)
    prev = tpo(prev_bars) if prev_bars else None
    comp = tpo(comp_bars)
    vwap = anchored_vwap(dev_bars)
    regime_4w = classify_regime(adjusted[-20:] if len(adjusted) >= 20 else adjusted, cfg)
    regime_dev = classify_regime(dev_bars, cfg)
    poc_migration = None
    if prev:
        d = dev["poc"] - prev["poc"]
        poc_migration = "higher" if d > 0 else ("lower" if d < 0 else "unchanged")
    prev_close = adjusted[-6]["close"] if len(adjusted) >= 6 else adjusted[0]["close"]
    return {
        "developing_tpo": dev,
        "previous_tpo": prev,
        "composite_tpo_4w": {"poc": comp["poc"], "vah": comp["vah"], "val": comp["val"]},
        "anchored_vwap": vwap,
        "opening_range": opening_range(dev_bars),
        "value_area_migration": poc_migration,
        "value_area_overlap": (bool(prev and dev["val"] < prev["vah"] and dev["vah"] > prev["val"])),
        "directional_efficiency": directional_efficiency(dev_bars),
        "realized_vol_annualized": realized_vol(adjusted),
        "weekly_open": adjusted[len(adjusted) - 5]["open"] if len(adjusted) >= 5 else None,
        "last_close": adjusted[-1]["close"],
        "prev_week_close": prev_close,
        "roll_dates": roll_dates,
        "regime_4w": regime_4w["regime"] if regime_4w else None,
        "regime_developing": regime_dev["regime"] if regime_dev else None,
        "atr": regime_dev["atr"] if regime_dev else None,
    }


def structure_score(struct: dict, cfg: dict) -> float | None:
    """Map structure to [-1, 1] (research hypothesis, configurable)."""
    try:
        dev = struct["developing_tpo"]
        last = struct["last_close"]
        parts: list[float] = []
        # position vs value area
        if last > dev["vah"]:
            parts.append(1.0)
        elif last < dev["val"]:
            parts.append(-1.0)
        else:
            parts.append((last - dev["poc"]) / ((dev["vah"] - dev["val"]) / 2.0 or 1e-9))
        # vwap position
        if struct.get("anchored_vwap"):
            parts.append(1.0 if last > struct["anchored_vwap"] else -1.0)
        # POC migration
        if struct.get("value_area_migration") == "higher":
            parts.append(0.5)
        elif struct.get("value_area_migration") == "lower":
            parts.append(-0.5)
        # weekly net direction
        if struct.get("atr"):
            net = struct["last_close"] - struct["prev_week_close"]
            parts.append(math.tanh(net / (cfg["scaling"]["trend_move_atr"] * struct["atr"])))
        if not parts:
            return None
        return max(-1.0, min(1.0, sum(parts) / len(parts)))
    except (KeyError, TypeError):
        return None
