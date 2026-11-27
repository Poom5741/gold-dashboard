# Verification Matrix — 001-gold-dashboard

Falsifiable completion predicate: every row below verified with real runtime evidence (pytest output, docker compose ps, curl on live VPS endpoints) recorded in evidence/.

| ID | Requirement (source) | Verification control | Evidence |
|----|----------------------|----------------------|----------|
| R1 | Backend FastAPI serves dashboard API + SQLite persistence (SPEC §8) | `docker compose up` → `curl /api/health` 200, `curl /api/bias` returns valid JSON with score −100..+100 | evidence/qa-*.md |
| R2 | Collectors: Yahoo (GC=F, DXY), FRED (DFII10/DGS10/DXY10Y), CFTC (6dca-aqww, code 088691), TVdataOptionOI (IV/25ΔRR/range only) | pytest with mocked HTTP; one live smoke run recorded (network available) | evidence/tests.txt |
| R3 | Bias engine: 5 dimensions, weights/thresholds from config; missing/stale data reduces reliability score explicitly, never silent neutral (SPEC §5) | pytest golden fixtures: score boundaries (±60/±20), stale-data fixture shows reliability drop + flagged dimension | evidence/tests.txt |
| R4 | Market structure: TPO/POC/VAH/VAL/VWAP/regime from daily bars (SPEC §4.1–4.2) | pytest fixtures with hand-computed expected POC/VAH/VAL on synthetic OHLC | evidence/tests.txt |
| R5 | Dashboard single page, mobile-friendly, sections per SPEC §6 | curl HTML 200 + contains 4 section mounts; viewport meta present | evidence/qa-*.md |
| R6 | Weekly report generator: text from computed metrics only, no LLM computation (SPEC §6) | pytest: report contains computed numbers identical to engine output; no network calls in generator (mock test) | evidence/tests.txt |
| R7 | Scheduler Asia/Bangkok: Sun 18:00 weekly brief, weekday 07:00 macro+price, weekday 14:00 options+bias (SPEC §7) | pytest: schedule construction asserts cron specs; endpoint /api/schedule returns configured jobs | evidence/tests.txt |
| R8 | No look-ahead bias in historical analysis (SPEC §9) | pytest: engine run on truncated history cannot see future rows (assert metrics for date T computed only from data ≤ T) | evidence/tests.txt |
| R9 | CME browser collector workflow: GitHub Actions Playwright collector with dry-run/mock mode; secrets CME_EMAIL/CME_PASSWORD optional, never requested | workflow YAML lint (actionlint or python yaml parse); dry-run job with mock fixture produces committed JSON schema-conformant; grep proves no credential echo | evidence/tests.txt |
| R10 | Historical snapshots replayable (SPEC §9) | API /api/snapshots lists stored runs; pytest writes 2 snapshots and replays bias from older snapshot | evidence/tests.txt |
| R11 | Freshness/flagging surfaced in API + UI (SPEC §9 "missing or stale clearly identified") | API /api/bias includes data_freshness per source with ok/stale/missing flags | evidence/qa-*.md |
| R12 | Independent QA in disposable clone (pipeline contract) | QA subagent clones candidate SHA in fresh dir, runs pytest + compose + curls, writes evidence report | evidence/qa-independent.md |
