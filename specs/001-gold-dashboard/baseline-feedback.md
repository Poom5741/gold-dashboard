# Baseline feedback loop — 001-gold-dashboard

Falsifiable predicate: `pytest -q` exits 0 with all declared controls passing, and `curl -sf http://localhost:8600/api/health` returns `{"status":"ok"}` from a running compose stack.

Baseline (pre-implementation): repo empty — pytest absent (invalid example: import error), no HTTP seam (curl connection refused). Both invalid examples recorded here before maker work.

Valid examples (declared):
- `pytest tests/test_bias_engine.py::test_stale_data_reduces_reliability` passes with golden fixture numbers.
- `curl -sf localhost:8600/api/health | jq -e '.status=="ok"'` exits 0.

The loop re-runs at every candidate commit; failures diagnose before fixes (self-healing loop, autonomous-execution policy).
