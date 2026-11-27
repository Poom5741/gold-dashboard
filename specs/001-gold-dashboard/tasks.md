# Tasks — 001-gold-dashboard

| ID | Task | Matrix refs | Status |
|----|------|-------------|--------|
| T1 | Repo scaffold: pyproject, deps, config/bias.yaml, docker-compose, Dockerfiles, .gitignore, README | REQ-1 | pending |
| T2 | Store: SQLite schema + DAO (price_bars, macro_series, cot, options_metrics, cme_snapshots, manual_imports, snapshots, reports) | REQ-1, REQ-10 | pending |
| T3 | Collectors: yahoo.py (GC=F, DX-Y.NYB), fred.py (DFII10, DGS10, DXY10Y), cftc.py (6dca-aqww, 088691) | REQ-2 | pending |
| T4 | Collectors: tvdataoption.py (ATM IV, 25Δ RR, implied weekly range only), cme_snapshots.py (data-branch JSON pull), manual_import.py (CSV: OI by strike, ETF flows) | REQ-2 | pending |
| T5 | Engine: structure.py — weekly TPO/POC/VAH/VAL, anchored VWAP (volume proxy), opening range, value-area migration, directional efficiency, realized vol; regime classifier (bull/bear/rotational/compression) | REQ-4 | pending |
| T6 | Engine: bias.py — 5 dimensions (structure, options skew, macro, COT, ETF), config weights, aggregate −100..+100, per-dimension reliability for stale/missing | REQ-3, REQ-11 | pending |
| T7 | Engine: report.py — weekly report answering SPEC §6's 7 questions from computed metrics | REQ-6 | pending |
| T8 | Scheduler: Asia/Bangkok Sun 18:00 brief, weekdays 07:00 macro+price, weekdays 14:00 options+bias + manual refresh endpoint | REQ-7 | pending |
| T9 | API: health, bias, structure, options, macro, snapshots, report/weekly, schedule, refresh; freshness flags in payloads | REQ-1, REQ-11 | pending |
| T10 | Frontend: Nuxt 3 single page, 4 sections, LightweightCharts + ECharts, mobile CSS | REQ-5 | pending |
| T11 | Tests: collectors (mocked), bias golden fixtures, structure fixtures, no-look-ahead, scheduler crons, report-numbers, snapshot replay | REQ-2, REQ-3, REQ-4, REQ-6, REQ-7, REQ-8, REQ-10 | pending |
| T12 | CME workflow: .github/workflows/cme-collector.yml — Playwright, dry-run/mock default, secrets-gated real run, commit snapshot to data/ branch; collector script + mock fixture + schema check | REQ-9 | pending |
| T13 | Self-verify: pytest full run, docker compose up on VPS, curl evidence | REQ-1, REQ-5, REQ-11 | pending |
| T14 | Independent QA in disposable clone (fresh subagent) + fix findings | REQ-12 | pending |
| T15 | Convergence, push GitHub, deploy, evidence pack | all | pending |
