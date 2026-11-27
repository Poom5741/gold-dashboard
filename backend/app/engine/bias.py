"""Directional bias engine — SPEC §5.

Five independent dimensions in [-1, 1]; weights from config; aggregate in
[-100, +100]. Missing/stale data REDUCES RELIABILITY visibly and weights
RENORMALIZE over usable dimensions (never silent neutral, D3/D4). Below the
reliability floor the headline label is "insufficient data — no directional
call". Every output carries per-source freshness (D7) and the config used (D14).
"""
from __future__ import annotations

import math

from ..collectors.base import combine, days_since, freshness, squash
from ..store import Store, json_dumps, utciso
from . import structure as st


def _dim(score, reliability: float, drivers: dict) -> dict:
    return {
        "score": None if score is None else round(score, 4),
        "reliability": round(reliability, 3),
        "drivers": drivers,
    }


def _stale_factor(as_of: str | None, limit_days: float, now) -> float:
    """Reliability multiplier: 1.0 fresh → decays to 0 at 2x the staleness limit."""
    if not as_of:
        return 0.0
    age = days_since(as_of, now)
    if age <= limit_days:
        return 1.0
    factor = 1.0 - (age - limit_days) / limit_days
    return max(0.0, factor)


def _series_score(rows: list[dict], value_key: str, invert: bool, scale: float) -> float | None:
    """Direction score from first differences of a stored series (older→newer)."""
    if len(rows) < 2:
        return None
    a, b = rows[0][value_key], rows[-1][value_key]
    if a is None or b is None:
        return None
    return squash((b - a) / (a if invert and a else 1.0) * (scale or 1.0), 1.0) \
        if invert else squash(b - a, scale)


# ---- dimensions ---------------------------------------------------------------
def dimension_structure(store: Store, as_of: str, cfg: dict, now) -> dict:
    limit = cfg["staleness_days"]["yahoo"]
    last = store.last_available("price_bars", as_of)
    f = freshness("yahoo", last, cfg["staleness_days"], now)
    fac = _stale_factor(last, limit, now)
    bars = store.bars("GC=F", as_of, limit=120)
    if len(bars) < 5 or fac <= 0:
        return _dim(None, 0.0, {"freshness": f, "reason": "insufficient history"})
    s = st.weekly_structure(bars, cfg)
    if not s:
        return _dim(None, 0.0, {"freshness": f, "reason": "insufficient history"})
    score = st.structure_score(s, cfg)
    return _dim(score, fac, {"freshness": f, "structure": s})


def dimension_options(store: Store, as_of: str, cfg: dict, now) -> dict:
    sub = cfg["dimensions"]["options"]["sub_weights"]
    parts: list[tuple[float, float]] = []
    drivers: dict = {}
    # sub-score skew: 25d RR primary, ATM IV level secondary signal
    opts = store.options(as_of, limit=10)
    last_opt = store.last_available("options_metrics", as_of)
    fac_tv = _stale_factor(last_opt, cfg["staleness_days"]["tv_options"], now)
    rr_scale = cfg["scaling"]["rr_scale"]
    if opts and fac_tv > 0:
        latest = opts[-1]
        rr = latest.get("rr25")
        skew_components: list[tuple[float, float]] = []
        if rr is not None:
            # positive RR = calls bid = bullish; scale 1 vol point -> ~0.46 score
            skew_components.append((squash(rr, rr_scale) or 0.0, 1.0))
        iv = latest.get("atm_iv")
        if iv is not None and latest.get("expected_range_low"):
            drivers["expected_range"] = [latest["expected_range_low"], latest["expected_range_high"]]
        if skew_components:
            parts.append((combine(skew_components), sub["skew"] * fac_tv))
        drivers["skew"] = {"rr25": rr, "atm_iv": iv, "freshness": freshness(
            "tv_options", last_opt, cfg["staleness_days"], now)}
    # sub-score oi: net call-put OI from manual imports
    oi_rows = store.manual("oi", "net_oi", as_of, limit=10) or []
    # aggregate per-strike rows into daily net OI if present
    daily_net: dict[str, float] = {}
    for r in store.manual("oi", "net_oi_daily", as_of, limit=10):
        daily_net[r["as_of"]] = r["value"]
    if not daily_net and oi_rows:
        strike_rows = []
        for s in {r["series"] for r in oi_rows}:
            strike_rows.append(store.manual("oi", s, as_of, limit=10))
        by_date: dict[str, float] = {}
        for series_rows in strike_rows:
            for r in series_rows:
                by_date[r["as_of"]] = by_date.get(r["as_of"], 0.0) + r["value"]
        daily_net = by_date
    if daily_net:
        ordered = sorted(daily_net.items())
        delta = ordered[-1][1] - (ordered[0][1] if len(ordered) > 1 else 0.0)
        oi_score = squash(delta, 5000.0)
        fac_oi = _stale_factor(ordered[-1][0], cfg["staleness_days"]["manual"], now)
        if oi_score is not None and fac_oi > 0:
            parts.append((oi_score, sub["oi"] * fac_oi))
        drivers["oi"] = {"net_change": delta, "note": "manual import only in MVP"}
    if not parts:
        return _dim(None, 0.0, {"reason": "no options data (skew + OI both unavailable)"})
    score = combine(parts)
    reliability = min(1.0, sum(w for _, w in parts) / sum(sub.values()))
    return _dim(score, reliability, drivers)


def dimension_macro(store: Store, as_of: str, cfg: dict, now) -> dict:
    parts: list[tuple[float, float]] = []
    drivers: dict = {}
    sc = cfg["scaling"]
    # real yields falling -> bullish gold
    real = store.macro("DFII10", as_of, limit=10)
    fac = _stale_factor(store.last_available("macro_series", as_of)
                        or (real[-1]["as_of"] if real else None),
                        cfg["staleness_days"]["fred"], now)
    if real and fac > 0:
        s = squash(real[-1]["value"] - real[0]["value"], sc["yield_scale"], invert=True)
        if s is not None:
            parts.append((s, 1.0 * fac))
        drivers["real_yield_change"] = round(real[-1]["value"] - real[0]["value"], 3)
    # nominal yields
    nom = store.macro("DGS10", as_of, limit=10)
    if nom and fac > 0:
        s = squash(nom[-1]["value"] - nom[0]["value"], sc["yield_scale"], invert=True)
        if s is not None:
            parts.append((s, 0.5 * fac))
    # dollar broad index falling -> bullish
    dxy = store.macro("DTWEXBGS", as_of, limit=10)
    if dxy and fac > 0:
        pct = (dxy[-1]["value"] - dxy[0]["value"]) / dxy[0]["value"] * 100.0
        s = squash(pct, sc["dxy_scale"] * 1.0, invert=True)
        if s is not None:
            parts.append((s, 1.0 * fac))
        drivers["dxy_pct_change"] = round(pct, 3)
    if not parts:
        return _dim(None, 0.0, {"reason": "no macro series available"})
    score = combine(parts)
    return _dim(score, min(1.0, fac), drivers)


def dimension_cot(store: Store, as_of: str, cfg: dict, now) -> dict:
    rows = store.cot(as_of, limit=60)
    last = rows[-1]["as_of"] if rows else None
    fac = _stale_factor(last, cfg["staleness_days"]["cot"], now)
    if len(rows) < 5 or fac <= 0:
        return _dim(None, 0.0, {"reason": "insufficient COT history", "freshness": freshness(
            "cot", last, cfg["staleness_days"], now)})
    net_now = rows[-1]["mm_long"] - rows[-1]["mm_short"]
    net_prev = rows[-2]["mm_long"] - rows[-2]["mm_short"]
    nets = sorted(r["mm_long"] - r["mm_short"] for r in rows)
    pct = 100.0 * sum(1 for n in nets if n <= net_now) / len(nets)
    sc = cfg["scaling"]
    s_pct = squash(pct - 50.0, sc["cot_pct_scale"])
    s_chg = squash(net_now - net_prev, sc["cot_change_scale"])
    parts = [(s, 1.0) for s in (s_pct, s_chg) if s is not None]
    if not parts:
        return _dim(None, 0.0, {"reason": "COT values unavailable"})
    score = combine(parts)
    return _dim(score, fac, {"net_mm": net_now, "net_change": net_now - net_prev,
                             "percentile": round(pct, 1),
                             "as_of": last,
                             "freshness": freshness("cot", last, cfg["staleness_days"], now)})


def dimension_etf(store: Store, as_of: str, cfg: dict, now) -> dict:
    # flows arrive under arbitrary series names (SPDR, IAU, …) — aggregate all
    rows = store.manual_kind("etf", as_of, limit=40)
    rows = sorted(rows, key=lambda r: (r["as_of"], r["series"]))
    last = rows[-1]["as_of"] if rows else None
    fac = _stale_factor(last, cfg["staleness_days"]["manual"], now)
    if len(rows) < 2 or fac <= 0:
        return _dim(None, 0.0, {"reason": "no ETF flow data (manual import)",
                                "freshness": freshness("manual", last, cfg["staleness_days"], now)})
    by_date: dict[str, float] = {}
    for r in rows:
        by_date[r["as_of"]] = by_date.get(r["as_of"], 0.0) + r["value"]
    dates = sorted(by_date)
    flow = sum(by_date[d] for d in dates[-5:])
    score = squash(flow, cfg["scaling"]["etf_flow_scale"])
    return _dim(score, fac, {"flow_tonnes_5d": flow,
                             "freshness": freshness("manual", last, cfg["staleness_days"], now)})


# ---- aggregate -----------------------------------------------------------------
def label_for(score: float, cfg: dict) -> str:
    t = cfg["thresholds"]
    if score >= t["strong_bull"]:
        return "Strong bullish"
    if score >= t["bull"]:
        return "Bullish"
    if score <= t["strong_bear"]:
        return "Strong bearish"
    if score <= t["bear"]:
        return "Bearish"
    return "Neutral"


def compute_bias(store: Store, as_of: str, cfg: dict, kind: str = "daily_bias",
                 now=None) -> dict:
    from datetime import datetime, timezone

    if isinstance(now, datetime):
        now_dt = now
    elif isinstance(now, str) and now:
        now_dt = datetime.fromisoformat(now)
    else:
        now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    dims = {
        "structure": dimension_structure(store, as_of, cfg, now),
        "options": dimension_options(store, as_of, cfg, now),
        "macro": dimension_macro(store, as_of, cfg, now),
        "cot": dimension_cot(store, as_of, cfg, now),
        "etf": dimension_etf(store, as_of, cfg, now),
    }
    usable = [(name, d) for name, d in dims.items()
              if d["score"] is not None and d["reliability"] > 0]
    total_weight = sum(w["weight"] for w in cfg["dimensions"].values())
    if usable:
        weights = cfg["dimensions"]
        pairs = [(d["score"], weights[name]["weight"]) for name, d in usable]
        aggregate = sum(s * w for s, w in pairs) / sum(w for _, w in pairs)
        score = round(max(-100.0, min(100.0, aggregate * 100.0)), 1)
        # SPEC §5: missing data reduces signal reliability — the weighted mean
        # (D4) runs over ALL five dimensions; absent ones carry reliability 0.0
        # in `dims` above, so coverage directly deflates the headline value.
        rel_pairs = [(d["reliability"], weights[name]["weight"]) for name, d in dims.items()]
        reliability = round(sum(r * w for r, w in rel_pairs) / total_weight, 3)
        renormalized = sorted(name for name, _ in usable)
    else:
        score, reliability, renormalized = None, 0.0, []
    floor = cfg["thresholds"]["reliability_floor"]
    if score is None or reliability < floor:
        label = "insufficient data — no directional call"
    else:
        label = label_for(score, cfg)
    # freshness across every stored source, including ones not scored
    freshness_map = {
        "yahoo": freshness("yahoo", store.last_available("price_bars", as_of),
                           cfg["staleness_days"], now),
        "fred": freshness("fred", store.last_available("macro_series", as_of),
                          cfg["staleness_days"], now),
        "cot": freshness("cot", store.last_available("cot", as_of),
                         cfg["staleness_days"], now),
        "tv_options": freshness("tv_options", store.last_available("options_metrics", as_of),
                                cfg["staleness_days"], now),
        "manual": freshness("manual", store.last_available("manual_imports", as_of),
                            cfg["staleness_days"], now),
    }
    return {
        "as_of": as_of,
        "kind": kind,
        "score": score,
        "label": label,
        "reliability": reliability,
        "dimensions_used": renormalized,
        "dimensions": dims,
        "data_freshness": freshness_map,
        "config_hash": cfg.get("_hash"),
        "generated_at": now,
    }
