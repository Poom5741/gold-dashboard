"""Collector tests — all external HTTP mocked (REQ-2)."""
import httpx
import pytest

from app.collectors import cftc, cme_snapshots, fred, manual_import, tvdataoption, yahoo
from app.collectors.base import CollectorError


# ---- yahoo -----------------------------------------------------------------
class FakeDF:
    def __init__(self, rows):
        import pandas as pd

        self.df = pd.DataFrame(rows, index=pd.to_datetime([r["date"] for r in rows]))


def test_yahoo_normalizes_and_marks_availability():
    import pandas as pd

    idx = pd.to_datetime(["2026-11-20", "2026-11-23"])
    df = pd.DataFrame(
        {"Open": [4000.0, 4010.0], "High": [4020.0, 4030.0], "Low": [3990.0, 4000.0],
         "Close": [4010.0, 4025.0], "Volume": [1000, 2000]}, index=idx)
    rows = yahoo.fetch("GC=F", fetcher=lambda s, p: df)
    assert rows[0]["date"] == "2026-11-20"
    assert rows[0]["available_at"].startswith("2026-11-20T23:59")
    assert rows[1]["close"] == 4025.0


def test_yahoo_raises_on_empty():
    import pandas as pd

    df = pd.DataFrame({"Open": [], "High": [], "Low": [], "Close": [], "Volume": []})
    with pytest.raises(CollectorError):
        yahoo.fetch("GC=F", fetcher=lambda s, p: df)


# ---- fred --------------------------------------------------------------------
FRED_CSV = "observation_date,DFII10\n2026-11-24,2.20\n2026-11-25,2.15\n2026-11-26,.\n"


def test_fred_parses_and_skips_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=FRED_CSV)

    rows = fred.fetch("DFII10", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert rows[-1]["value"] == 2.15
    assert rows[-1]["available_at"].startswith("2026-11-26T00:00")  # +1 day lag


def test_fred_rejects_bad_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>error: DXY10Y not found</html>")

    with pytest.raises(CollectorError):
        fred.fetch("DFII10", client=httpx.Client(transport=httpx.MockTransport(handler)))


# ---- cftc ---------------------------------------------------------------------
CFTC_JSON = [
    {"report_date_as_yyyy_mm_dd": "2026-11-17T00:00:00.000",
     "cftc_contract_market_code": "088691",
     "m_money_positions_long_all": "210051",
     "m_money_positions_short_all": "43919",
     "open_interest_all": "407834"},
]


def test_cftc_parses_full_prefixed_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "cftc_contract_market_code=088691" in str(request.url)
        return httpx.Response(200, json=CFTC_JSON)

    rows = cftc.fetch(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert rows[0]["mm_long"] == 210051.0
    assert rows[0]["as_of"] == "2026-11-17"
    assert rows[0]["available_at"].startswith("2026-11-20T00:00")  # +3d release lag


# ---- tvdataoption ---------------------------------------------------------------
def test_tv_rr25_and_atm_iv():
    chain = [
        # today's expiry (dte 0) must be skipped — expiry noise, not weekly signal
        {"dte": 0, "delta": 0.50, "iv": 0.55},
        {"dte": 7, "delta": 0.25, "iv": 0.20},
        {"dte": 7, "delta": -0.25, "iv": 0.18},
        {"dte": 7, "delta": 0.50, "iv": 0.19},  # ATM = closest |delta| to 0.5
    ]
    rows = tvdataoption.fetch(spot=4000.0, chain_fetcher=lambda s: chain)
    assert rows[0]["rr25"] == pytest.approx(2.0)  # (0.20-0.18)*100
    assert rows[0]["atm_iv"] == pytest.approx(19.0)
    lo, hi = rows[0]["expected_range_low"], rows[0]["expected_range_high"]
    assert lo < 4000.0 < hi


def test_tv_raises_without_iv():
    with pytest.raises(CollectorError):
        tvdataoption.fetch(spot=4000.0, chain_fetcher=lambda s: [{"dte": 7}])


# ---- cme snapshots ---------------------------------------------------------------
def test_cme_snapshot_validation_and_provenance():
    store_payload = {
        "snapshot_date": "2026-11-26", "tenor": "GC1!", "source": "mock",
        "oi_by_strike": [{"strike": 4000, "call_oi": 10, "put_oi": 5}],
    }
    cme_snapshots.validate_snapshot(store_payload)
    with pytest.raises(CollectorError):
        cme_snapshots.validate_snapshot({"snapshot_date": "2026-11-26"})


def test_cme_fetch_from_mock_server():
    payload = {"snapshot_date": "2026-11-26", "tenor": "GC1!", "source": "real",
               "oi_by_strike": []}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/snapshots/2026-11-26.json"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = cme_snapshots.fetch("https://example/raw/repo/data", token="t", client=client)
    assert out[0]["source"] == "real"


def test_cme_fetch_requires_token_semantics_documented():
    # probe finds nothing -> CollectorError (private repo without token 404s)
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(CollectorError):
        cme_snapshots.fetch("https://example/raw/repo/data", token="", client=client)


# ---- manual import -----------------------------------------------------------------
def test_manual_import_validates_and_idempotent(store):
    good = "date,series,tonnes\n2026-11-21,SPDR,5.2\n2026-11-24,SPDR,-3.1\n"
    n = manual_import.import_text(store, "etf", good)
    assert n >= 1
    n2 = manual_import.import_text(store, "etf", good)  # idempotent re-import
    rows = store.manual("etf", "SPDR", "2026-12-01", limit=10)
    assert len(rows) == 2
    assert n2 >= 1
    with pytest.raises(CollectorError):
        manual_import.import_text(store, "etf", "date,value\n2026-11-21,5\n")
    with pytest.raises(CollectorError):
        manual_import.import_text(store, "etf", "date,series,tonnes\nnot-a-date,SPDR,1\n")


def test_manual_calendar_import():
    store_cal = "date,time,event,impact\n2026-12-01,20:30,US CPI,high\n"
    rows_parsed = manual_import.parse_csv("calendar", store_cal)
    assert rows_parsed[0]["event"] == "US CPI"
