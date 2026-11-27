#!/usr/bin/env python3
"""CME browser collector (runs on GitHub Actions ONLY).

Mock mode (default until CME_EMAIL/CME_PASSWORD secrets exist): emits the
committed mock fixture tagged source="mock" (production backend rejects it, D2).
Real mode: Playwright logs into CME SSO (login.cmegroup.com), opens QuikStrike
Vol2Vol for the front tenor, reads the OI chain + expected range, and writes a
snapshot tagged source="real".

Approach only — no code copied from unlicensed repos (C4).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

MOCK_FIXTURE = Path(__file__).parent / "mock_snapshot.json"


def write_snapshot(payload: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    payload.setdefault("snapshot_date", date.today().isoformat())
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"snapshot written: {out} (source={payload.get('source')})")


def collect_mock(out: Path) -> dict:
    with open(MOCK_FIXTURE, "r", encoding="utf-8") as f:
        payload = json.load(f)
    payload["snapshot_date"] = date.today().isoformat()
    payload["source"] = "mock"
    write_snapshot(payload, out)
    return payload


def collect_real(out: Path) -> dict:
    """Real CME login via Playwright. Requires CME_EMAIL/CME_PASSWORD env.

    NEVER prints credential material. Raises on missing secrets.
    """
    email, password = os.environ.get("CME_EMAIL"), os.environ.get("CME_PASSWORD")
    if not email or not password:
        sys.exit("real mode requires CME_EMAIL/CME_PASSWORD secrets (never embedded)")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(locale="en-US")
        page = ctx.new_page()
        page.goto("https://login.cmegroup.com/sso/login")
        page.fill("#username", email)
        page.fill("#password", password)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        # Vol2Vol expected-range tool (QuikStrike embed)
        page.goto(
            "https://www.cmegroup.com/tools-information/quikstrike/"
            "vol2vol-expected-range.html"
        )
        page.wait_for_load_state("networkidle")
        # NOTE: selectors below are best-effort; CME's DOM changes — verify on
        # first real run and update before trusting output (accepted risk R9).
        tenor = page.locator("select.tenor-selector option").first.get_attribute("value")
        rows = page.eval_on_selector_all(
            "table.oi-table tbody tr",
            "rows => rows.map(r => { const c = r.querySelectorAll('td');"
            " return { strike: parseFloat(c[0]?.innerText),"
            " call_oi: parseFloat(c[1]?.innerText.replace(/,/g,'')) || 0,"
            " put_oi: parseFloat(c[2]?.innerText.replace(/,/g,'')) || 0 }; })",
        )
        payload = {
            "snapshot_date": date.today().isoformat(),
            "tenor": tenor or "GC1!",
            "source": "real",
            "oi_by_strike": [r for r in rows if r.get("strike")],
            "vol2vol": {},
        }
        browser.close()
    write_snapshot(payload, out)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("mock", "real"), default="mock")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    if args.mode == "real":
        collect_real(out)
    else:
        collect_mock(out)


if __name__ == "__main__":
    main()
