"""API smoke: create_app on a seeded in-memory-ish store serves valid payloads (REQ-1/11)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(store, cfg, tmp_path, monkeypatch):
    from app.main import build_app
    from app.config import Settings

    st = Settings(env={"GOLD_SCHEDULER": "false", "GOLD_DB_PATH": str(tmp_path / "api.db")})
    app = build_app(store=store, settings=st, cfg=cfg, with_scheduler=False)
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_bias_endpoint_payload_contract(client):
    r = client.get("/api/bias")
    assert r.status_code == 200
    b = r.json()
    if b["score"] is not None:
        assert -100 <= b["score"] <= 100
    assert b["label"]
    assert "data_freshness" in b and "dimensions" in b
    for src, f in b["data_freshness"].items():
        assert f["status"] in ("ok", "stale", "missing")


def test_schedule_endpoint(client, cfg):
    r = client.get("/api/schedule")
    assert r.status_code == 200
    jobs = r.json()["jobs"]
    assert jobs["weekly_brief"]["hour"] == 18
    assert r.json()["timezone"] == "Asia/Bangkok"


def test_snapshots_replay_via_api(store, cfg, client):
    from test_bias_engine import seed_world

    seed_world(store)
    from app.engine.bias import compute_bias

    b = compute_bias(store, "2026-11-21T00:00:00+00:00", cfg,
                     now="2026-11-21T06:00:00+00:00")
    import json

    from app.config import config_hash

    sid = store.save_snapshot("daily_bias", "2026-11-21",
                              b, json.dumps({k: v for k, v in cfg.items() if not k.startswith("_")},
                                            sort_keys=True), config_hash(cfg))
    lst = client.get("/api/snapshots").json()
    assert any(row["id"] == sid for row in lst)
    detail = client.get(f"/api/snapshots/{sid}")
    assert detail.status_code == 200
    assert detail.json()["payload"]["score"] == b["score"]
    missing = client.get("/api/snapshots/99999")
    assert missing.status_code == 404


def test_mock_cme_snapshot_rejected_by_default(store, client, cfg):
    from test_bias_engine import seed_world

    seed_world(store)
    import json

    from app.collectors import cme_snapshots

    cme_snapshots.store_snapshots(store, [{
        "snapshot_date": "2026-11-20", "tenor": "GC1!", "source": "mock",
        "oi_by_strike": [{"strike": 4000, "call_oi": 1, "put_oi": 2}]}])
    r = client.get("/api/options")
    assert r.status_code == 200
    assert r.json()["cme_snapshot"] is None  # prod default rejects mock (D2)


def test_manual_import_via_raw_body(store, client, cfg):
    csv = "date,series,tonnes\n2026-11-21,SPDR,4.2\n2026-11-24,SPDR,-1.1\n"
    r = client.post("/api/import/etf", content=csv.encode(),
                    headers={"Content-Type": "text/csv"})
    assert r.status_code == 200 and r.json()["rows"] == 2
    r = client.post("/api/import/etf", content=b"not,a,header\n1,2,3\n")
    assert r.status_code == 400


def test_weekly_report_lists_known_upcoming_calendar(store, cfg, client):
    csv = "date,time,event,impact\n2026-12-04,21:30,US Nonfarm Payrolls,high\n"
    r = client.post("/api/import/calendar", content=csv.encode())
    assert r.status_code == 200
    r = client.get("/api/report/weekly")
    assert r.status_code == 200
    assert "US Nonfarm Payrolls" in r.text  # future event, known at import time
