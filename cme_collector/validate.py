#!/usr/bin/env python3
"""Snapshot schema + provenance validator (workflow gate)."""
import json
import sys
from pathlib import Path

REQUIRED = {"snapshot_date", "tenor", "source", "oi_by_strike"}


def main() -> None:
    path = Path(sys.argv[1])
    payload = json.loads(path.read_text())
    missing = REQUIRED - set(payload)
    if missing:
        sys.exit(f"FAIL: missing keys {sorted(missing)}")
    if payload["source"] not in ("real", "mock"):
        sys.exit(f"FAIL: bad provenance {payload['source']!r}")
    if not isinstance(payload["oi_by_strike"], list):
        sys.exit("FAIL: oi_by_strike must be a list")
    for row in payload["oi_by_strike"]:
        if not isinstance(row, dict) or "strike" not in row:
            sys.exit("FAIL: oi row without strike")
    print(f"OK: schema valid, provenance={payload['source']}, "
          f"{len(payload['oi_by_strike'])} strikes")


if __name__ == "__main__":
    main()
