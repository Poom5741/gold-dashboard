# Gold Weekly Intelligence Dashboard (MVP)

Web-based gold market intelligence: free-source macro / institutional
positioning / options / market-structure data aggregated into an explainable
weekly directional bias. Research tool — not a trading terminal.

Read `specs/001-gold-dashboard/spec.md` (canonical requirements) and
`specs/001-gold-dashboard/decisions.md` (ratified decisions) first.

## Run (VPS)

```bash
docker compose up -d --build          # backend :8600, frontend :8601 (127.0.0.1 only)
# browser via SSH tunnel:
ssh -L 8600:127.0.0.1:8600 -L 8601:127.0.0.1:8601 <vps>
# open http://localhost:8601
```

## API

| Endpoint | What |
|---|---|
| `GET /api/health` | liveness |
| `GET /api/bias` | current bias: score −100..+100, label, per-dimension scores + reliability, data freshness flags |
| `GET /api/structure` | weekly TPO/POC/VAH/VAL (daily-bar approximation), VWAP, regime, roll flags |
| `GET /api/options` | ATM IV / 25Δ RR history, expected range, CME OI snapshot (provenance-badged) |
| `GET /api/macro` | DFII10 / DGS10 / DTWEXBGS, COT, ETF flows |
| `GET /api/snapshots` + `/api/snapshots/{id}` | historical bias snapshots (replayable, config-pinned) |
| `GET /api/report/weekly` | deterministic weekly report (answers SPEC §6's 7 questions) |
| `GET /api/schedule` | configured jobs (Asia/Bangkok) |
| `POST /api/refresh` | manual collect-all (fan-in: a failing source is flagged, others proceed) |
| `POST /api/import/{kind}` | manual CSV import: kind ∈ `oi`, `etf`, `calendar` |

## Data sources (all free, DECISIONS.md)

Yahoo (GC=F, DX-Y.NYB) · FRED CSV no-key (DFII10, DGS10, **DTWEXBGS** — `DXY10Y`
does not exist on FRED, live-verified substitution) · CFTC Disaggregated COT
(dataset 6dca-aqww, gold `cftc_contract_market_code=088691`) · TradingView
options chain via TVdataOptionOI (MIT; IV/25ΔRR/expected range only — TV has no
GC options OI) · CME OI snapshots via GitHub Actions browser collector.

## Manual imports (curl examples)

```bash
curl -X POST localhost:8600/api/import/etf --data 'date,series,tonnes
2026-11-21,SPDR,4.2'
curl -X POST localhost:8600/api/import/calendar --data 'date,time,event,impact
2026-12-01,20:30,US CPI,high'
curl -X POST localhost:8600/api/import/oi --data 'date,strike,call_oi,put_oi
2026-11-26,4000,5200,6300'
```

## CME collector

The CME browser collector runs on **GitHub Actions only** (never from the VPS —
CME 403-blocks datacenter IPs and ToU forbids scraping). Default mode is mock
(provenance `"mock"`; the production backend rejects mock snapshots). Real mode
activates automatically once Poom adds `CME_EMAIL` / `CME_PASSWORD` repo
secrets — verify selectors on the first real run (documented accepted risk).

**Workflow install (one-time):** the file ships at
`cme_collector/cme-collector.workflow.yml` because the automation token used
for this push lacks the `workflow` scope GitHub requires before it may create
`.github/workflows/*`. Install it with either:

```bash
mkdir -p .github/workflows && cp cme_collector/cme-collector.workflow.yml .github/workflows/cme-collector.yml && git add .github && git commit -m "install cme collector workflow" && git push
```

or by uploading the file via the GitHub web UI (Add file → Create new file →
`.github/workflows/cme-collector.yml`), then add the two secrets.

## Bias engine

5 dimensions (structure 30%, options 30%, macro 20%, COT 15%, ETF 5%),
weights/thresholds in `backend/config/bias.yaml` — research hypotheses, NOT
validated parameters. Missing/stale data reduces reliability visibly; weights
renormalize over present dimensions; below the 0.5 reliability floor the
headline becomes "insufficient data — no directional call" (never silent
neutral). Every snapshot stores the config it used (reproducible replay).
No look-ahead: engines filter `as_of <= T AND available_at <= T` (publication-
aware) and only use completed daily bars.

## Tests

```bash
cd backend && python -m pytest -q
```

## Known limitations (MVP)

- TPO/POC/VAH/VAL are daily-bar volume-proxy approximations (labeled as such).
- Options OI positioning requires manual import until the CME collector's real
  mode is verified with Poom's secrets.
- ETF flows + economic calendar are manual CSV imports.
- TradingView anonymous scanner dependency: pacing + backoff, but an IP block
  would flag the options skew source missing until it clears.
