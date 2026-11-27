# Plan — 001-gold-dashboard (micro route, compact)

Canonical requirement source: specs/001-gold-dashboard/spec.md (Poom's SPEC.md, verbatim). Decisions already ratified: specs/001-gold-dashboard/decisions.md.

## Architecture (decided)

```
GitHub Actions (Poom5741/gold-dashboard)         VPS (this host, docker)
└─ cme-collector.yml (Playwright)                └─ docker compose (port 8600)
   ├─ dry-run/mock by default (mock fixture         ├─ backend (FastAPI + APScheduler + SQLite)
   │  JSON committed to data/ branch)               │   ├─ collectors: yahoo, fred, cftc, tvdataoption (in-process),
   └─ real run only when CME_EMAIL/CME_PASSWORD     │   │   cme_snapshots (pull JSON from data/ branch), manual import
      secrets present (Poom adds later)             │   ├─ bias engine (weights/thresholds from config/bias.yaml)
                                                    │   └─ weekly report generator (metrics → text, no LLM math)
                                                    └─ frontend (Nuxt 3 static, proxies /api → backend)
```

## Backend layout

- `backend/app/main.py` — FastAPI: /api/health, /api/bias, /api/structure, /api/options, /api/macro, /api/snapshots, /api/report/weekly, /api/schedule, /api/refresh (manual trigger)
- `backend/app/collectors/` — yahoo.py, fred.py, cftc.py, tvdataoption.py, cme_snapshots.py, manual_import.py; each returns typed rows + `as_of` timestamp; failures raise `CollectorError` (never silently empty)
- `backend/app/engine/` — structure.py (TPO/POC/VAH/VAL/VWAP/regime from daily bars), bias.py (5 dimensions, config weights, reliability scoring for stale/missing), report.py (weekly report text from computed metrics)
- `backend/app/store.py` — SQLite (WAL): tables price_bars, macro_series, cot, options_metrics, cme_snapshots, manual_imports, snapshots(bias runs), reports
- `backend/app/scheduler.py` — APScheduler cron in Asia/Bangkok: Sun 18:00 weekly brief; Mon–Fri 07:00 macro+price; Mon–Fri 14:00 options+bias
- `backend/config/bias.yaml` — weights (30/30/20/15/5), thresholds (±60/±20), staleness limits per source
- `tests/` — collectors (respx/mocked httpx), bias golden fixtures, structure hand-computed fixtures, no-look-ahead, scheduler crons, report numbers == engine numbers

## Frontend layout

- `frontend/` Nuxt 3 + TS single page `pages/index.vue`; sections: Weekly Overview / Market Structure / Options / Macro & Positioning (SPEC §6); charts via TradingView Lightweight Charts + Apache ECharts (CDN); mobile-first CSS; polls /api/* endpoints.

## Data correctness rules

- Every stored row carries `as_of` + `collected_at`; freshness = now − as_of vs per-source staleness limit in config → ok/stale/missing flags surfaced in API + UI.
- Missing/stale dimension → reliability score reduced visibly (per-dimension reliability 0..1, aggregate reliability = weighted), NOT neutral.
- No look-ahead: engine functions take `as_of` and only use rows ≤ as_of; test asserts truncated-future data changes nothing.
- Report generator formats numbers computed by engine; contains no arithmetic of its own beyond string formatting.

## Verification strategy

Matrix rows REQ-1–REQ-12 (specs/001-gold-dashboard/matrix.md). Baseline feedback loop = `pytest` + live `curl /api/health`; every feature lands behind a failing test first where practical (collectors/bias/structure/report/scheduler are pure-Python TDD; compose/UI verified by runtime evidence).

## Goldfish review design rulings (27 Nov 2026, binding for implementation)

Two fresh-context goldfish reviewers stress-tested the design; the following rulings are adopted:

- **D1 — schedule gap:** add Saturday 07:00 refresh (price + COT + manual imports) so the Sunday 18:00 brief uses Friday's close and the latest COT release; the Sunday job runs data refresh before report generation. Weekday specs per SPEC §7 unchanged.
- **D2 — snapshot provenance:** every cme_snapshots row carries `source: "mock"|"real"`. Config `cme_accept_mock: false` (production) rejects mock rows; UI badges mock data. Mock fixtures never enter the real table.
- **D3 — options dimension sub-scores:** sub-score A = skew/IV (25ΔRR, ATM IV, implied range — automated via TVdataOptionOI); sub-score B = OI positioning (manual import only). Within-dimension weights renormalize over present sub-scores; per-sub-score reliability.
- **D4 — aggregate semantics:** dimension weights renormalize over dimensions with usable data (reliability > 0); aggregate reliability = weighted mean of dimension reliabilities; if aggregate reliability < 0.5 the headline label is "insufficient data — no directional call" instead of a bucket label.
- **D5 — publication-aware no-look-ahead:** rows carry `as_of` (data date) AND `available_at` (earliest time the value could be known: COT release date, FRED as_of+1d, Yahoo session close). Engine filters `as_of <= T AND available_at <= T`. Freshness compares now against expected publication cadence, not retrieval time.
- **D6 — roll handling:** detect GC=F roll gaps; back-adjust (difference splice) for structure metrics; roll weeks flagged in structure output.
- **D7 — staleness limits per cadence (config):** yahoo 3 trading days, fred 4 calendar days, cot 10 days, tv options 3 days, manual 14 days, calendar 30 days.
- **D8 — scheduler recovery:** misfire_grace_time=3600, coalesce=True, startup catch-up (weekly brief older than 8 days or daily bias older than 2 days → regenerate on boot).
- **D9 — refresh fan-in:** each collector failure marks that source missing (freshness=missing, reliability impact) and the refresh continues; only an all-collectors failure fails the job.
- **D10 — workflow hygiene:** cme-collector.yml sets `permissions: contents: write`, a `concurrency: cme-collector` group, UTC cron (documented Asia/Bangkok equivalents), real run gated on both secrets present. Backend snapshot pull REQUIRES a token for a private data branch (`GITHUB_DATA_TOKEN` env); no "token optional".
- **D11 — TPO approximation labeling:** value-area algorithm pinned: POC = daily-bar volume-proxy price bucket with max volume; VA = smallest band around POC covering 70% of proxy volume (two-sided expansion). UI labels POC/VAH/VAL "daily-bar approximation".
- **D12 — completed bars only:** engine inputs exclude any bar dated today (exchange time) — forming bars never enter metrics.
- **D13 — economic calendar:** manual CSV import path (date, time, event, impact); weekly report question 7 answered from imported calendar, else explicitly "calendar data not imported".
- **D14 — snapshot reproducibility:** each bias snapshot stores the full bias config (weights/thresholds/floors) + SHA-256 of it; replay uses the snapshotted config, never live config.
- **D15 — report generator deterministic-only:** MVP ships no LLM client at all; report.py formats engine metrics. Test asserts no network/LLM calls and numbers identical to engine output.
- **D16 — manual import validation:** schema + date sanity checks, idempotent upsert keyed (source, series, date), provenance `source: "manual"`.
- **D17 — TradingView fragility:** request pacing + bounded retries/backoff in tvdataoption collector; on failure the options skew sub-score is flagged missing (reliability impact), never fabricated.
- **D18 — FRED series substitution:** `DXY10Y` does not exist on FRED (live-verified 27 Nov 2026: returns HTML error; DFII10/DGS10/DTWEXBGS verified live) → use **DTWEXBGS** (Broad US Dollar Index, daily) as the FRED dollar series; DXY spot still from Yahoo (DX-Y.NYB).
- **D19 — network exposure:** compose binds ports to 127.0.0.1 on the host; access via SSH tunnel. Documented accepted risk if Poom wants LAN exposure.
