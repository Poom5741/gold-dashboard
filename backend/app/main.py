"""FastAPI application — the only public seam (HTTP + in-process scheduler)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .config import Settings, load_config
from .engine import report as report_mod
from .engine.bias import compute_bias
from .scheduler import build_scheduler, job_specs, startup_catchup
from .scheduler_refresher import run_refresh
from .store import Store

STATE: dict = {}


def build_app(store: Store | None = None, settings: Settings | None = None,
              cfg: dict | None = None, with_scheduler: bool | None = None) -> FastAPI:
    store = store or Store(os.environ.get("GOLD_DB_PATH", "data/gold.db"))
    settings = settings or Settings()
    cfg = cfg or load_config()
    if with_scheduler is None:
        with_scheduler = settings.scheduler_enabled

    def refresh() -> dict:
        return run_refresh(store, settings)

    def bias(as_of: str, kind: str = "daily_bias") -> dict:
        import json as _json

        from .config import config_hash as _hash

        b = compute_bias(store, as_of, cfg, kind=kind)
        config_json = _json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")},
                                  sort_keys=True)
        store.save_snapshot(kind, as_of, b, config_json, _hash(cfg))
        return b

    def weekly_report(bias_payload: dict | None = None) -> str:
        b = bias_payload or bias(datetime.now(timezone.utc).isoformat(), "weekly_brief")
        struct = (b.get("dimensions", {}).get("structure", {}).get("drivers", {})
                  or {}).get("structure")
        cal = store.calendar_upcoming(b["as_of"], limit=30)
        text = report_mod.weekly_report(b, struct, cal)
        store.save_report("weekly", b["as_of"], text)
        return text

    STATE.update({"store": store, "settings": settings, "cfg": cfg})

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        sched = None
        if with_scheduler:
            sched = build_scheduler(store, settings, cfg, refresh, bias, weekly_report)
            actions = startup_catchup(store, refresh, bias, weekly_report, cfg)
            STATE["catchup"] = actions
            sched.start()
            STATE["sched"] = sched
        yield
        if sched:
            sched.shutdown(wait=False)

    app = FastAPI(title="Gold Weekly Intelligence Dashboard", version="0.1.0",
                  lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    class RefreshBody(BaseModel):
        targets: list[str] | None = None

    @app.get("/api/health")
    def health():
        return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}

    @app.get("/api/bias")
    def bias_endpoint(as_of: str | None = None):
        as_of = as_of or datetime.now(timezone.utc).isoformat()
        return compute_bias(store, as_of, cfg, kind="daily_bias")

    @app.get("/api/structure")
    def structure_endpoint(as_of: str | None = None):
        from .engine import structure as st

        as_of = as_of or datetime.now(timezone.utc).isoformat()
        bars = store.bars("GC=F", as_of, limit=120)
        if len(bars) < 5:
            raise HTTPException(503, "insufficient history for structure metrics")
        return st.weekly_structure(bars, cfg)

    @app.get("/api/options")
    def options_endpoint(as_of: str | None = None):
        as_of = as_of or datetime.now(timezone.utc).isoformat()
        rows = store.options(as_of, limit=30)
        snaps = store.cme_snapshots(as_of, accept_mock=settings.cme_accept_mock)
        oi_by_strike = []
        if snaps:
            oi_by_strike = (snaps[0].get("payload") and
                            __import__("json").loads(snaps[0]["payload"]).get("oi_by_strike", []))
        return {"history": rows, "latest": rows[-1] if rows else None,
                "cme_snapshot": snaps[0] if snaps else None, "oi_by_strike": oi_by_strike}

    @app.get("/api/macro")
    def macro_endpoint(as_of: str | None = None):
        as_of = as_of or datetime.now(timezone.utc).isoformat()
        out = {}
        for s in ("DFII10", "DGS10", "DTWEXBGS"):
            rows = store.macro(s, as_of, limit=60)
            out[s] = rows
        cot = store.cot(as_of, limit=60)
        etf = store.manual_kind("etf", as_of, limit=60)
        gc_bars = store.bars("GC=F", as_of, limit=90)
        return {"series": out, "cot": cot, "etf_flows": etf, "gc_bars": gc_bars}

    @app.get("/api/snapshots")
    def snapshots_endpoint(kind: str | None = None, limit: int = 50):
        rows = store.snapshots(kind, limit)
        return [{"id": r["id"], "created_at": r["created_at"], "as_of": r["as_of"],
                 "kind": r["kind"], "score": r["score"], "label": r["label"],
                 "reliability": r["reliability"], "config_hash": r["config_hash"]}
                for r in rows]

    @app.get("/api/snapshots/{snapshot_id}")
    def snapshot_detail(snapshot_id: int):
        import json

        r = store.get_snapshot(snapshot_id)
        if not r:
            raise HTTPException(404, "snapshot not found")
        r["payload"] = json.loads(r["payload"])
        return r

    @app.get("/api/report/weekly", response_class=PlainTextResponse)
    def weekly_report_endpoint():
        reports = store.reports("weekly", limit=1)
        if not reports:
            return weekly_report()
        return reports[0]["text"]

    @app.get("/api/reports")
    def reports_endpoint(kind: str | None = None):
        return store.reports(kind, limit=50)

    @app.get("/api/schedule")
    def schedule_endpoint():
        return {"jobs": job_specs(cfg), "timezone": "Asia/Bangkok",
                "catchup_actions": STATE.get("catchup", [])}

    @app.post("/api/refresh")
    def refresh_endpoint(body: RefreshBody | None = None):
        return run_refresh(store, settings)

    @app.post("/api/import/{kind}")
    async def import_endpoint(kind: str, request: Request, text: str | None = None):
        from .collectors import manual_import

        # CSV may arrive as the raw request body (README curl examples) or as
        # the ?text= query parameter — both are accepted.
        raw = text if text is not None else (await request.body()).decode("utf-8", "replace")
        try:
            n = manual_import.import_text(store, kind, raw)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(400, str(exc))
        return {"status": "ok", "rows": n}

    return app


app = None
if __name__ != "__main__":
    pass


def create_app() -> FastAPI:  # uvicorn target: backend.app.main:create_app
    return build_app()
