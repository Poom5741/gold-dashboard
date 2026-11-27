"""Weekly Intelligence Report generator — deterministic formatting ONLY (D15).

Answers SPEC §6's seven questions from computed metrics. No LLM client exists
in this codebase; no network calls; no arithmetic beyond rounding values the
engine already computed. Tests assert numbers here match engine output.
"""
from __future__ import annotations


def _fmt(v, suffix: str = "", digits: int = 1) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{round(v, digits)}{suffix}"
    return f"{v}{suffix}"


def _dir_word(score: float | None) -> str:
    if score is None:
        return "no directional call"
    if score >= 60:
        return "strongly bullish"
    if score >= 20:
        return "bullish"
    if score <= -60:
        return "strongly bearish"
    if score <= -20:
        return "bearish"
    return "neutral"


def weekly_report(bias: dict, struct: dict | None, calendar_rows: list[dict] | None) -> str:
    dims = bias.get("dimensions", {})
    st_ = (dims.get("structure", {}).get("drivers", {}) or {}).get("structure") or struct
    freshness = bias.get("data_freshness", {})
    lines: list[str] = []

    # Q1 — what happened last week
    if st_:
        move = None
        if st_.get("last_close") is not None and st_.get("prev_week_close"):
            move = st_["last_close"] - st_["prev_week_close"]
        lines.append("## 1. What happened last week")
        lines.append(
            f"Gold closed the week at {_fmt(st_.get('last_close'), '', 1)} "
            f"(prev close {_fmt(st_.get('prev_week_close'), '', 1)}, "
            f"{_fmt(move, '', 1)} w/w). POC {_fmt(st_.get('developing_tpo', {}).get('poc'))}, "
            f"VAH {_fmt(st_.get('developing_tpo', {}).get('vah'))}, "
            f"VAL {_fmt(st_.get('developing_tpo', {}).get('val'))} (daily-bar approximation). "
            f"Value area migrated {st_.get('value_area_migration') or 'n/a'} vs prior week"
            f"{', with overlap' if st_.get('value_area_overlap') else ', without overlap'}. "
            f"4-week regime: {st_.get('regime_4w') or 'n/a'}; developing week: "
            f"{st_.get('regime_developing') or 'n/a'}."
        )
        if st_.get("roll_dates"):
            lines.append(f"Note: contract roll detected ({', '.join(st_['roll_dates'])}); "
                         "structure metrics are roll-adjusted.")
    else:
        lines.append("## 1. What happened last week")
        lines.append("Market-structure data insufficient (need >= 5 completed daily bars).")

    # Q2 — what is happening this week
    lines.append("## 2. What is happening this week")
    lines.append(
        f"Aggregate bias {_fmt(bias.get('score'), '', 0)} ({bias.get('label')}) at reliability "
        f"{_fmt((bias.get('reliability') or 0) * 100 if bias.get('reliability') is not None else None, '%', 0)}. "
        f"Dimensions used: {', '.join(bias.get('dimensions_used') or []) or 'none'}."
    )
    exp = (dims.get("options", {}).get("drivers", {}) or {}).get("skew", {})
    lo = exp.get("expected_range_low") if isinstance(exp, dict) else None
    hi = exp.get("expected_range_high") if isinstance(exp, dict) else None
    if lo and hi:
        lines.append(f"Implied weekly expected range (from ATM IV): {lo:.0f} – {hi:.0f}.")

    # Q3 — what is driving gold
    lines.append("## 3. What is driving gold")
    drivers: list[str] = []
    m = dims.get("macro", {}).get("drivers", {})
    if isinstance(m, dict):
        if m.get("real_yield_change") is not None:
            drivers.append(f"10Y real yield {m['real_yield_change']:+.2f}pts w/w "
                           f"({'supportive' if m['real_yield_change'] < 0 else 'a headwind'} for gold)")
        if m.get("dxy_pct_change") is not None:
            drivers.append(f"broad dollar {m['dxy_pct_change']:+.1f}% w/w")
    c = dims.get("cot", {}).get("drivers", {})
    if isinstance(c, dict) and c.get("net_mm") is not None:
        drivers.append(f"managed-money net {c['net_mm']:.0f} contracts "
                       f"({c.get('percentile')} pct of {c.get('as_of')}-window, "
                       f"change {c.get('net_change'):+.0f} w/w)")
    e = dims.get("etf", {}).get("drivers", {})
    if isinstance(e, dict) and e.get("flow_tonnes_5d") is not None:
        drivers.append(f"ETF flows {e['flow_tonnes_5d']:+.0f}t over 5 sessions")
    o = dims.get("options", {}).get("drivers", {})
    if isinstance(o, dict) and o.get("skew", {}).get("rr25") is not None:
        drivers.append(f"25d risk reversal {o['skew']['rr25']:+.1f} vol pts")
    lines.append("; ".join(drivers) if drivers else "No driver data available.")

    # Q4 — which direction has stronger evidence
    lines.append("## 4. Which direction has stronger evidence")
    per_dim = []
    for name in ("structure", "options", "macro", "cot", "etf"):
        d = dims.get(name, {})
        s, r = d.get("score"), d.get("reliability")
        per_dim.append(f"{name}: {_fmt(s, '', 2)} (reliability {r if r is not None else 'n/a'})")
    lines.append("; ".join(per_dim) + f". Aggregate evidence is {_dir_word(bias.get('score'))}.")

    # Q5 — which price levels matter
    if st_:
        dev = st_.get("developing_tpo", {})
        lines.append("## 5. What price levels matter")
        lines.append(
            f"VAL {_fmt(dev.get('val'))} / POC {_fmt(dev.get('poc'))} / VAH {_fmt(dev.get('vah'))}; "
            f"weekly anchored VWAP {_fmt(st_.get('anchored_vwap'))}; opening range "
            f"{_fmt((st_.get('opening_range') or {}).get('low'))}–"
            f"{_fmt((st_.get('opening_range') or {}).get('high'))}."
        )
    else:
        lines.append("## 5. What price levels matter")
        lines.append("Insufficient structure data.")

    # Q6 — what would invalidate the bias
    lines.append("## 6. What would invalidate the bias")
    invalidations: list[str] = []
    if st_:
        dev = st_.get("developing_tpo", {})
        if bias.get("score") is not None and bias["score"] > 0:
            invalidations.append(f"acceptance below VAL {_fmt(dev.get('val'))}")
            invalidations.append(f"POC migration lower ({st_.get('value_area_migration')})")
        elif bias.get("score") is not None and bias["score"] < 0:
            invalidations.append(f"acceptance above VAH {_fmt(dev.get('vah'))}")
            invalidations.append("POC migration higher")
        else:
            invalidations.append("decisive value-area acceptance in either direction")
    invalidations.append("real yields breaking their weekly direction")
    invalidations.append("a sharp dollar reversal")
    lines.append("; ".join(invalidations) + ".")

    # Q7 — upcoming events
    lines.append("## 7. What upcoming events could change the bias")
    if calendar_rows:
        events = "; ".join(
            f"{r['date']} {r.get('event', '')} ({r.get('impact', 'n/a')})"
            for r in sorted(calendar_rows, key=lambda r: r["date"])[:10]
        )
        lines.append("Imported calendar: " + events + ".")
    else:
        lines.append("Calendar data not imported — run the manual calendar CSV import "
                     "(see README) or this section stays explicit about the gap (D13).")

    # freshness footer
    stale = {k: v for k, v in freshness.items() if v.get("status") != "ok"}
    lines.append("---")
    if stale:
        flagged = ", ".join(f"{k}: {v['status']}" for k, v in stale.items())
        lines.append(f"Data freshness flags: {flagged}.")
    else:
        lines.append("All data sources fresh.")
    return "\n".join(lines)
