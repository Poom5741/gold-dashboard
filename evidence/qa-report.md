# Independent QA — gold-dashboard (disposable clone /tmp/gold-qa-clone)

Date: 2026-11-27 · Clone of /root/workspace/gold-dashboard (clean, master) · Repo untouched.

## Test suite
- `cd backend && python -m pytest -q` → **38 passed in 6.14s** (clean clone, no code changes).
- Running pytest from the repo root fails (`ModuleNotFoundError: app`) — README documents `cd backend && pytest`, so DX nit only.

## Runtime verification (in-process TestClient, seeded temp DB)
- All 9 endpoints return 200 with sane payloads (health, bias, structure, options, macro, snapshots, schedule, report/weekly, reports).
- /api/bias: score 68.4 "Strong bullish", reliability 0.73, freshness map surfaced; COT missing correctly reported `missing` when absent.
- Weekly report: deterministic, all 7 questions, numbers match engine values, freshness footer, explicit "calendar data not imported" fallback works.
- Docker/compose: ports bound 127.0.0.1:8600/8601 (D19 ✓); backend Dockerfile path/config wiring verified by inspection (not built here).

## Confirmed bugs
1. **HIGH — Manual OI imports never reach the bias engine.** `manual_import.py` stores per-strike series `strike_<N>` (value = call_oi − put_oi), but `engine/bias.py:88-100` queries series `net_oi` / `net_oi_daily`, which never exist. The fallback that aggregates strike series derives its series set from the same `net_oi` query, so it is unreachable. Repro'd: importing OI per the README curl example → options dimension stays `score=None, reliability=0.0, "no options data"`. D3 sub-score B (OI positioning) is effectively dead code; only the TV skew sub-score can ever score.
2. **MEDIUM — `/api/macro` `etf_flows` always empty for real imports.** `main.py:118` reads series `etf_flows` only; the README example imports series `SPDR`. Repro'd: 0 rows returned while the ETF *engine* dimension (which correctly uses `manual_kind`) scores fine. UI would show no ETF flows despite data present.
3. **MEDIUM — Frontend missing SPEC §6 elements.** No ETF-flow display and no economic-calendar display anywhere in `pages/index.vue`; "significant strikes" / call-put distribution not shown beyond the OI heatmap. Present and correct: bias/score/reliability, regimes, expected range, freshness pills, daily-bar-approximation label, CME mock/real badge, RR + IV chart, COT chart.
4. **LOW — Weekly report text carries no date.** The stored report has no "week ending / generated at" header; SPEC §7 requires source timestamps and a preserved report is ambiguous about which week it covers (metadata exists only in the reports table).
5. **LOW — `report.py:_dir_word` hardcodes ±60/±20** duplicating `bias.yaml` thresholds (replay uses the bias label from the snapshotted config, so impact is cosmetic wording only).
6. **LOW — dead code:** `bias.py:_series_score` unused; `collectors/base.py:next_weekday` unused.
7. **NIT — macro dimension uses one shared staleness factor** for DFII10/DGS10/DTWEXBGS (last across all macro_series), so per-series staleness isn't distinguished; yahoo "3 trading days" implemented as 3 calendar days.

## SPEC / decision compliance (§4–§7, §9, D1–D19)
- D1 Sat 07:00 refresh ✓ (config `mon-fri,sat`), weekly brief refresh-first ✓; D8 misfire_grace/coalesce/catch-up ✓ (tested).
- D2 provenance `cme-mock`/`cme-real`, production rejects mock ✓ (tested); CME collector default = mock fixture, real mode gated on secrets, GH-Actions-only ✓.
- D3 sub-score renormalization ✓ for skew; **broken for OI (bug 1)**.
- D4 aggregate reliability weighted over ALL five dims ✓ — macro-only → reliability 0.2 and headline suppressed, explicitly tested.
- D5/D12 no look-ahead: `as_of` + `available_at` everywhere; future-row injection changes nothing at fixed T; publication lag test ✓. Completed-bars filter `date < as_of-date` ✓ (conservative).
- D6 roll back-adjustment + flags ✓; D7 per-cadence staleness config ✓; D9 fan-in ✓ (cme skip w/o token doesn't count as failure); D10 workflow permissions/concurrency/UTC cron/token-required ✓; D11 approximation labeled in API+UI ✓; D13 calendar import path ✓; D14 config_json + SHA-256 pinned replay ✓ (tested reproducible); D15 no LLM client, no-network test ✓; D16 CSV validation + idempotent upsert ✓; D18 DTWEXBGS ✓; D19 localhost binding ✓.
- §9 acceptance: no paid sources ✓; missing/stale reduces reliability (tested) ✓; snapshots for replay ✓; reproducible metrics ✓; auto weekly brief ✓ (scheduler); stale-data identification ✓ (freshness flags + report footer).

## Verdict
Implementation is faithful to SPEC/decisions with strong test coverage (38 tests incl. no-look-ahead, staleness, floor suppression, replay reproducibility). Ship-blocker before real use: **bug 1** (OI imports never influence the options dimension — one of the two options sub-scores silently never scores). Bugs 2–3 degrade the dashboard's evidence surface (ETF/calendar missing from UI).
