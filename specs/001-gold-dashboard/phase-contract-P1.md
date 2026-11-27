# Phase contract — 001-gold-dashboard / P1-mvp

## Outcome
A deployed dashboard on Poom's VPS: docker compose up brings up backend+frontend; the API exposes bias with visible evidence and freshness flags; weekly brief text generated from computed metrics; pytest suite green including no-look-ahead.

## Native Spec Kit links
- Specification requirement IDs: REQ-1–REQ-12 (specs/001-gold-dashboard/matrix.md)
- Plan section: specs/001-gold-dashboard/plan.md
- Task IDs: T1–T15 (specs/001-gold-dashboard/tasks.md)

## Scope boundary
- In scope: MVP scope items 1–7 of kanban card t_d058408b.
- Explicitly out of scope: SPEC §10 items; Telegram notifications; backtesting engine.
- Assumptions / decisions to confirm: none open (DECISIONS.md closed all).

## Research and domain grounding
- Repository evidence / upstream source: specs/001-gold-dashboard/research-sources.md (live checks from this VPS, 27 Nov 2026).
- Open question and owner: none.

## Delivery lane
- Dependency baseline SHA: (fresh repo, no baseline)
- Classification: sequential (single maker checkout)
- Shared paths: backend/, frontend/, .github/workflows/, docker-compose.yml
- Maker / independent checker: dev (Hermes) / independent QA subagent (fresh context, disposable clone)

## Definition of done
- Required tests and runtime journeys: pytest all green; docker compose up; curl /api/health, /api/bias, /api/report/weekly, /api/snapshots 200 with valid payloads.
- Required evidence/proof-pack entries: evidence/self-verify.md, evidence/qa-independent.md, evidence/lenses-1.json, evidence/convergence-1.json, evidence/release-1.md.
- Required design/security/manual review gates: goldfish review receipt; no secrets in repo; no CME scraping from VPS.
- Milestone audit question: does each matrix row have real runtime evidence?
