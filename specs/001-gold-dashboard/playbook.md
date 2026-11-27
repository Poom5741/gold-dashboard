# Delivery playbook — 001-gold-dashboard

## Outcome and scope

User confirmation and provenance: Kanban card t_d058408b (dispatcher-spawned) quoting SPEC.md verbatim as canonical + DECISIONS.md recording Poom's ratified decisions (27 Nov 2026). Purpose gate confirmed against this provenance.
Affected people and success signal: Poom (sole user) opens the dashboard on his VPS and sees a daily directional bias with visible evidence, fresh data timestamps, and a Sunday weekly brief — no paid data subscriptions.
Non-goals: automated trade execution, real-time tick streaming, paid feeds, ML prediction, broker integration, position management (SPEC §10).
Route and escalation triggers: micro (playbook + matrix, compact convergence). Escalate to native planning only if unresolved consequential scope or cross-boundary design appears (none expected — DECISIONS.md closed all open questions).
Selected pinned playbook: ask-super-speckit playbook-delivery (micro route), PStack investigate/implement methods as lenses.
Completion predicate: every matrix row R1–R12 verified with real runtime evidence; independent QA in a disposable clone passes; convergence receipt recorded.
Authority, budget and limits: single checkout /root/workspace/gold-dashboard; deploy on this VPS via docker compose on a free port (chosen: 8600); no scraping CME from VPS; no touching rakazo containers/pgdata; no copying code from unlicensed repos; CME secrets never requested.

## Steps

| Step | Dependencies | Owner | Pending/completed/skipped | Evidence or skip reason |
| --- | --- | --- | --- | --- |
| 1. Investigation (data sources) | — | prior research worker | completed | specs/001-gold-dashboard/research-sources.md (RESEARCH.md, 27 Nov 2026, live tests from this VPS) |
| 2. Spec + decisions frozen | 1 | Poom | completed | specs/001-gold-dashboard/spec.md (= SPEC.md), decisions.md |
| 3. Plan + tasks | 2 | dev | completed | specs/001-gold-dashboard/plan.md, tasks.md |
| 4. Learning checkpoint + goldfish review | 3 | dev + 2 fresh subagents | completed | evidence/learn-1.json, evidence/goldfish-1.json |
| 5. Personas selected | 4 | dev | completed | .super-speckit state via select-personas |
| 6. Implement (backend, collectors, bias engine, frontend, workflows, compose, tests) | 5 | dev | completed | git candidate commit |
| 7. Self-verification (pytest, compose up, curl) | 6 | dev | completed | evidence/self-verify.md |
| 8. Independent QA in disposable clone | 7 | independent QA subagent | completed | evidence/qa-independent.md |
| 9. Lenses (pstack + lude specialist) + reconciliation | 8 | dev | completed | evidence/lenses-1.json |
| 10. Compact convergence | 9 | dev | completed | evidence/convergence-1.json |
| 11. Release: push GitHub, deploy VPS, evidence pack | 10 | dev | completed | evidence/release-1.md |

## Research and architecture

Actual entry points, callers and durable-state owners: FastAPI app (`backend/app.main:app`) is the only public seam (HTTP + APScheduler in-process); SQLite file `data/gold.db` owned by backend container; frontend Nuxt 3 static build served by its own container proxying `/api` to backend; GitHub Actions workflow `cme-collector.yml` owns CME snapshots → commits to `data/` branch; backend pulls snapshots via GitHub raw (token optional).
Relevant primary/local sources and resulting choices: RESEARCH.md live checks → Yahoo/FRED/CFTC/TVdataOptionOI automated; OI-by-strike + ETF flows manual CSV import adapters; CME snapshots via Actions only.
Allowed dependencies and public interfaces: yfinance, httpx, pandas, APScheduler, FastAPI, uvicorn, tvdataoption (MIT, pinned), pytest; TradingView Lightweight Charts + ECharts via CDN in Nuxt page.
Executable checks and observed invalid/valid examples: pytest suite (collectors mocked, bias golden fixtures, no-look-ahead), `curl /api/health` 200 valid example; bias score outside −100..+100 = invalid.
Narrow exceptions and review: CME collector on VPS is forbidden (403 + ToU) — workflow is dry-run/mock only until Poom adds secrets.

## Acceptance

| Requirement ID | User journey or public seam | Expected observation | Evidence | Status |
| --- | --- | --- | --- | --- |
| R1–R12 | see specs/001-gold-dashboard/matrix.md | every row's control passes with real runtime output | evidence/qa-independent.md + evidence/self-verify.md | pass |

Independent engineering review and findings/dispositions: recorded in evidence/qa-independent.md and evidence/lenses-1.json (dispositions fixed/accepted-risk/dismissed with reasons).
Relevant usability coverage and non-applicable rationales: single-user internal tool; mobile-friendly single page verified via HTML/viewport checks; no multi-user auth in scope (VPS-local).

## Continuation

Current candidate, stage and next action: see .super-speckit/state/work-state.yml; after convergence → push to GitHub Poom5741/gold-dashboard and deploy.
Observed host runner/wake mechanism, or unavailable: single kanban run, no overnight continuation.
Checkpoint and decision trail: DECISIONS.md + this playbook.
Blockers and resume conditions: none; if docker build fails on RAM, reduce Nuxt build parallelism (NODE_OPTIONS=--max-old-space-size=2048).
