# Gold Weekly Intelligence Dashboard — MVP Specification

> Source: Poom's spec (27 พ.ย. 2026) — verbatim, canonical. Worker ต้อง implement ตามนี้

## 1. Objective

Build a web-based gold market intelligence dashboard that aggregates macroeconomic, institutional positioning, options and market structure data to establish a weekly directional bias for gold trading.

The system is a research and decision-support tool, not a real-time trading terminal or automated trading bot.

## 2. Core Requirements

- Zero paid market data subscriptions for the MVP.
- Automated data collection wherever possible.
- Weekly market intelligence report.
- Daily options positioning updates.
- Historical data persistence for future backtesting.
- Mobile-friendly, single-page dashboard.
- Explainable directional bias supported by underlying evidence.

## 3. Data Sources

| Data | Source | Frequency |
|---|---|---|
| Gold OHLC | Yahoo Finance / MT5 | Daily |
| Gold intraday OHLC | MT5 | Daily |
| Dollar Index (DXY) | Yahoo Finance | Daily |
| US real yields | FRED | Daily |
| US Treasury yields | FRED | Daily |
| COT positioning | CFTC API | Weekly |
| Gold ETF flows | World Gold Council | Weekly |
| Options open interest | CME QuikStrike | Daily |
| 25-delta risk reversal | CME Vol2Vol | Daily |
| Implied volatility | CME Vol2Vol | Daily |
| Economic calendar | Free external source | Daily |

## Existing Projects Investigated (see RESEARCH.md for full findings)

- https://github.com/Hewkaw02/Gold-Sight-by-OI — no license; approach reference only
- https://github.com/bodytaylor/xau-oi-lab — no license; approach reference only
- https://github.com/Hewkaw02/TVdataOptionOI — **MIT, use as dependency**

Evaluate existing data collectors before implementing new ones. Support manual data import as a fallback.

## 4. Analytics Modules

### 4.1 Market Structure
- Developing weekly TPO; previous weekly TPO; rolling four-week composite TPO
- POC, VAH and VAL
- Weekly anchored VWAP or tick-volume proxy
- Weekly opening range
- Value area migration and overlap
- Weekly directional efficiency
- Realized volatility

### 4.2 Market Regime
Classify into: Bullish trend / Bearish trend / Rotational / Compression.
Four-week regime and developing weekly regime classified independently.

### 4.3 Options Intelligence
- OI by strike and expiration; call/put OI distribution; daily & weekly OI changes
- Nearest significant upper/lower OI levels
- 25-delta risk reversal and changes; ATM implied volatility
- Implied expected weekly price range
- Do NOT assume high OI attracts or repels price

### 4.4 Institutional Positioning
- Managed money net positioning; weekly long/short changes
- Historical positioning percentile; ETF inflows/outflows

### 4.5 Macroeconomic Intelligence
- DXY / real yield / Treasury yield direction
- Upcoming high-impact events; weekly driver summary

## 5. Directional Bias Engine

Five independent dimensions, each score −1..+1:

| Dimension | Initial weight |
|---|---|
| Weekly market structure | 30% |
| Options positioning and skew | 30% |
| Macroeconomic conditions | 20% |
| Institutional positioning | 15% |
| ETF flows | 5% |

Weighted aggregate −100..+100 → Strong bullish +60..+100 / Bullish +20..+59 / Neutral ±19 / Bearish −20..−59 / Strong bearish −60..−100.

Weights and thresholds configurable — research hypotheses, NOT validated parameters.
**Missing or stale data must reduce signal reliability rather than silently become neutral.**

## 6. Dashboard Layout

**Weekly Overview:** bias, aggregate score, 4-week regime, developing regime, expected range, data freshness.
**Market Structure:** weekly/composite TPO viz, POC migration, S/R levels, VWAP.
**Options:** OI heatmap, call/put distribution, significant strikes, RR history, IV history.
**Macro & Positioning:** DXY/real yield trends, COT, ETF flows, calendar.

**Weekly Intelligence Report** must answer:
1. What happened last week? 2. What is happening this week? 3. What is driving gold?
4. Which direction has stronger evidence? 5. What price levels matter?
6. What would invalidate the bias? 7. What upcoming events could change it?

## 7. Update Schedule (Asia/Bangkok UTC+7)

| Schedule | Task |
|---|---|
| Sunday 18:00 | Generate initial weekly brief |
| Weekdays 14:00 | Refresh daily options and directional bias |
| Weekdays 07:00 | Refresh macro and historical price data |
| Manual | Refresh on demand |

Preserve previous reports; display source timestamps; flag delayed data.

## 8. Technical Stack

- Backend: Python + FastAPI
- Frontend: Nuxt 3 + TypeScript
- Database: SQLite
- Charts: TradingView Lightweight Charts + Apache ECharts
- Scheduler: APScheduler or cron
- Deployment: Docker Compose
- LLM: optional, for readable reports from calculated metrics only — **must not invent data or compute scores itself**

## 9. MVP Acceptance Criteria

- Dashboard runs on a single VPS
- No mandatory paid data subscriptions
- Weekly brief generated automatically
- Daily directional bias supported by visible evidence
- Historical snapshots available for replay
- Missing or stale data clearly identified
- All calculated metrics reproducible
- No look-ahead bias in historical analysis

## 10. Out of Scope

Automated trade execution; real-time tick streaming; paid feeds; ML price prediction; broker integration; position management.

## 11. Future Extensions

HMM regime; Monte Carlo first-passage between OI levels; bias accuracy tracking; backtesting; Telegram notifications; prop firm risk calculator.
