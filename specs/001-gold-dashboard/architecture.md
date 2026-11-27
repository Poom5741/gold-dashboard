# Architecture receipt — 001-gold-dashboard (micro)

Decision: single-repo compose architecture (ratified in decisions.md §"สถาปัตยกรรมที่สอดคล้องกับการตัดสินใจ" + goldfish rulings D1–D19 in plan.md).

- Entry point / public seam: FastAPI `/api/*` (backend container), proxied by Nuxt 3 static frontend; compose binds 127.0.0.1:8600 (D19).
- Data plane: collectors in-process (yahoo/fred/cftc/tvdataoption/cme_snapshots/manual_import) → SQLite WAL (`data/gold.db`) via store.py; rows carry `as_of` + `available_at` + `source` provenance (D5, D2, D16).
- Engine plane: structure.py (TPO/POC/VAH/VAL/VWAP/regime from completed daily bars, roll-adjusted, D6/D11/D12), bias.py (5 weighted dimensions, renormalized over present, reliability floor, D3/D4), report.py (deterministic formatting, D15).
- Scheduler plane: APScheduler in-process, Asia/Bangkok cron: Sat+Mon–Fri 07:00 macro+price, Mon–Fri 14:00 options+bias, Sun 17:55 refresh → 18:00 weekly brief; misfire/coalesce/catch-up per D8.
- External plane: GitHub Actions `cme-collector.yml` (Playwright, permissions contents:write, concurrency group, UTC cron, dry-run/mock default, provenance-tagged snapshots) → data branch → backend pull with required `GITHUB_DATA_TOKEN` (D10).
- Alternatives rejected: scraping CME from VPS (403 + ToU, decisions.md); paid feeds (SPEC §2 forbids); separate private data repo (same-repo data branch is simpler and decisions.md allows either).

Evidence: specs/001-gold-dashboard/plan.md (architecture + rulings), specs/001-gold-dashboard/decisions.md, specs/001-gold-dashboard/architecture.mmd.
