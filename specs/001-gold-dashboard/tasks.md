# Tasks — 001-gold-dashboard

| ID | Task | Matrix refs | Status |
|----|------|-------------|--------|
| T1 | Repo scaffold: pyproject, deps, config/bias.yaml, docker-compose, Dockerfiles, .gitignore, README | R1 | pending |
| T2 | Store: SQLite schema + DAO (price_bars, macro_series, cot, options_metrics, cme_snapshots, manual_imports, snapshots, reports) | R1, R10 | pending |
| T3 | Collectors: yahoo.py (GC=F, DX-Y.NYB), fred.py (DFII10, DGS10, DXY10Y), cftc.py (6dca-aqww, 088691) | R2 | pending |
| T4 | Collectors: tvdataoption.py (ATM IV, 25Δ RR, implied weekly range only), cme_snapshots.py (data-branch JSON pull), manual_import.py (CSV: OI by strike, ETF flows) | R2 | pending |
| T5 | Engine: structure.py — weekly TPO/POC/VAH/VAL, anchored VWAP (volume proxy), opening range, value-area migration, directional efficiency, realized vol; regime classifier (bull/bear/rotational/compression) | R4 | pending |
| T6 | Engine: bias.py — 5 dimensions (structure, options skew, macro, COT, ETF), config weights, aggregate −100..+100, per-dimension reliability for stale/missing | R3, R11 | pending |
| T7 | Engine: report.py — weekly report answering SPEC §6's 7 questions from computed metrics | R6 | pending |
| T8 | Scheduler: Asia/Bangkok Sun 18:00 brief, weekdays 07:00 macro+price, weekdays 14:00 options+bias + manual refresh endpoint | R7 | pending |
| T9 | API: health, bias, structure, options, macro, snapshots, report/weekly, schedule, refresh; freshness flags in payloads | R1, R11 | pending |
| T10 | Frontend: Nuxt 3 single page, 4 sections, LightweightCharts + ECharts, mobile CSS | R5 | pending |
| T11 | Tests: collectors (mocked), bias golden fixtures, structure fixtures, no-look-ahead, scheduler crons, report-numbers, snapshot replay | R2, R3, R4, R6, R7, R8, R10 | pending |
| T12 | CME workflow: .github/workflows/cme-collector.yml — Playwright, dry-run/mock default, secrets-gated real run, commit snapshot to data/ branch; collector script + mock fixture + schema check | R9 | pending |
| T13 | Self-verify: pytest full run, docker compose up on VPS, curl evidence | R1, R5, R11 | pending |
| T14 | Independent QA in disposable clone (fresh subagent) + fix findings | R12 | pending |
| T15 | Convergence, push GitHub, deploy, evidence pack | all | pending |
