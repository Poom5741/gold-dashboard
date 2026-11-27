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

Matrix rows R1–R12 (specs/001-gold-dashboard/matrix.md). Baseline feedback loop = `pytest` + live `curl /api/health`; every feature lands behind a failing test first where practical (collectors/bias/structure/report/scheduler are pure-Python TDD; compose/UI verified by runtime evidence).
