"""SQLite persistence layer. Every stored row carries:
- as_of: the market data date the value describes,
- available_at: earliest time the value could have been known (publication-aware, D5),
- collected_at: when we fetched it,
- source: provenance tag (yahoo/fred/cftc/tv/manual/cme-mock/cme-real).
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS price_bars (
  symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
  close REAL, volume REAL, source TEXT NOT NULL,
  as_of TEXT NOT NULL, available_at TEXT NOT NULL, collected_at TEXT NOT NULL,
  PRIMARY KEY (symbol, date)
);
CREATE TABLE IF NOT EXISTS macro_series (
  series TEXT NOT NULL, date TEXT NOT NULL, value REAL, source TEXT NOT NULL,
  as_of TEXT NOT NULL, available_at TEXT NOT NULL, collected_at TEXT NOT NULL,
  PRIMARY KEY (series, date)
);
CREATE TABLE IF NOT EXISTS cot (
  as_of TEXT PRIMARY KEY, available_at TEXT NOT NULL, collected_at TEXT NOT NULL,
  mm_long REAL, mm_short REAL, open_interest REAL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS options_metrics (
  as_of TEXT PRIMARY KEY, available_at TEXT NOT NULL, collected_at TEXT NOT NULL,
  atm_iv REAL, rr25 REAL, expected_range_low REAL, expected_range_high REAL,
  oi_call REAL, oi_put REAL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cme_snapshots (
  snapshot_date TEXT NOT NULL, tenor TEXT NOT NULL, payload TEXT NOT NULL,
  source TEXT NOT NULL,  -- 'cme-mock' | 'cme-real' (D2)
  as_of TEXT NOT NULL, available_at TEXT NOT NULL, collected_at TEXT NOT NULL,
  PRIMARY KEY (snapshot_date, tenor)
);
CREATE TABLE IF NOT EXISTS manual_imports (
  kind TEXT NOT NULL, series TEXT NOT NULL, date TEXT NOT NULL, value REAL,
  source TEXT NOT NULL, as_of TEXT NOT NULL, available_at TEXT NOT NULL,
  collected_at TEXT NOT NULL, event TEXT, impact TEXT, PRIMARY KEY (kind, series, date)
);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, as_of TEXT NOT NULL,
  kind TEXT NOT NULL,             -- 'weekly_brief' | 'daily_bias'
  score REAL, label TEXT, reliability REAL,
  payload TEXT NOT NULL,          -- full bias output JSON (dimensions, freshness, structure...)
  config_json TEXT NOT NULL,      -- bias config used (D14)
  config_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, as_of TEXT NOT NULL,
  kind TEXT NOT NULL, text TEXT NOT NULL
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utciso(dt: datetime | None = None) -> str:
    dt = dt or utcnow()
    return dt.astimezone(timezone.utc).isoformat()


class Store:
    """Thin thread-safe DAO over sqlite3 (WAL)."""

    def __init__(self, path: str | Path = "data/gold.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
            # lightweight migration: columns added post-MVP-schema (event/impact)
            existing = {r[1] for r in self._conn.execute(
                "PRAGMA table_info(manual_imports)").fetchall()}
            for col, ddl in (("event", "TEXT"), ("impact", "TEXT")):
                if existing and col not in existing:
                    self._conn.execute(f"ALTER TABLE manual_imports ADD COLUMN {col} {ddl}")
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # -- generic upsert helpers -------------------------------------------
    def _upsert(self, table: str, row: dict, key_cols: list[str]) -> None:
        cols = list(row.keys())
        updates = [c for c in cols if c not in key_cols]
        sql = (
            f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) "
            f"ON CONFLICT({','.join(key_cols)}) DO UPDATE SET "
            + ",".join(f"{c}=excluded.{c}" for c in updates)
        )
        with self._lock:
            self._conn.execute(sql, [row[c] for c in cols])
            self._conn.commit()

    # -- price bars --------------------------------------------------------
    def upsert_bars(self, symbol: str, bars: list[dict], source: str) -> int:
        now = utciso()
        n = 0
        for b in bars:
            self._upsert(
                "price_bars",
                {
                    "symbol": symbol, "date": b["date"], "open": b["open"], "high": b["high"],
                    "low": b["low"], "close": b["close"], "volume": b.get("volume"),
                    "source": source, "as_of": b["date"], "available_at": b["available_at"],
                    "collected_at": now,
                },
                ["symbol", "date"],
            )
            n += 1
        return n

    def bars(self, symbol: str, as_of: str, limit: int = 120) -> list[dict]:
        """Completed bars only, publication-aware: as_of <= T AND available_at <= T (D5, D12)."""
        rows = self._conn.execute(
            "SELECT * FROM price_bars WHERE symbol=? AND date<=? AND date < ? "
            "AND available_at<=? ORDER BY date DESC LIMIT ?",
            (symbol, as_of, as_of[:10], as_of, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # -- macro -------------------------------------------------------------
    def upsert_macro(self, series: str, rows: list[dict], source: str) -> int:
        now = utciso()
        n = 0
        for r in rows:
            self._upsert(
                "macro_series",
                {"series": series, "date": r["date"], "value": r["value"], "source": source,
                 "as_of": r["date"], "available_at": r["available_at"], "collected_at": now},
                ["series", "date"],
            )
            n += 1
        return n

    def macro(self, series: str, as_of: str, limit: int = 30) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM macro_series WHERE series=? AND as_of<=? AND available_at<=? "
            "ORDER BY as_of DESC LIMIT ?",
            (series, as_of, as_of, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # -- COT ----------------------------------------------------------------
    def upsert_cot(self, rows: list[dict], source: str) -> int:
        now = utciso()
        n = 0
        for r in rows:
            self._upsert(
                "cot",
                {"as_of": r["as_of"], "available_at": r["available_at"], "collected_at": now,
                 "mm_long": r.get("mm_long"), "mm_short": r.get("mm_short"),
                 "open_interest": r.get("open_interest"), "source": source},
                ["as_of"],
            )
            n += 1
        return n

    def cot(self, as_of: str, limit: int = 60) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM cot WHERE as_of<=? AND available_at<=? ORDER BY as_of DESC LIMIT ?",
            (as_of, as_of, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # -- options -------------------------------------------------------------
    def upsert_options(self, rows: list[dict], source: str) -> int:
        now = utciso()
        n = 0
        for r in rows:
            self._upsert(
                "options_metrics",
                {"as_of": r["as_of"], "available_at": r["available_at"], "collected_at": now,
                 "atm_iv": r.get("atm_iv"), "rr25": r.get("rr25"),
                 "expected_range_low": r.get("expected_range_low"),
                 "expected_range_high": r.get("expected_range_high"),
                 "oi_call": r.get("oi_call"), "oi_put": r.get("oi_put"), "source": source},
                ["as_of"],
            )
            n += 1
        return n

    def options(self, as_of: str, limit: int = 30) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM options_metrics WHERE as_of<=? AND available_at<=? "
            "ORDER BY as_of DESC LIMIT ?",
            (as_of, as_of, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # -- CME snapshots ---------------------------------------------------------
    def upsert_cme_snapshot(self, snapshot_date: str, tenor: str, payload: dict,
                            source: str, available_at: str) -> None:
        self._upsert(
            "cme_snapshots",
            {"snapshot_date": snapshot_date, "tenor": tenor, "payload": json_dumps(payload),
             "source": source, "as_of": snapshot_date, "available_at": available_at,
             "collected_at": utciso()},
            ["snapshot_date", "tenor"],
        )

    def cme_snapshots(self, as_of: str, accept_mock: bool = False,
                      tenor: str | None = None) -> list[dict]:
        """Mock-provenance snapshots are excluded unless explicitly accepted (D2)."""
        q = ("SELECT * FROM cme_snapshots WHERE as_of<=? AND available_at<=? ")
        args: list = [as_of, as_of]
        if not accept_mock:
            q += "AND source!='cme-mock' "
        if tenor:
            q += "AND tenor=? "
            args.append(tenor)
        q += "ORDER BY as_of DESC"
        return [dict(r) for r in self._conn.execute(q, args).fetchall()]

    # -- manual imports ---------------------------------------------------------
    def upsert_manual(self, kind: str, series: str, rows: list[dict]) -> int:
        """Idempotent upsert keyed (kind, series, date); provenance source='manual' (D16)."""
        now = utciso()
        n = 0
        for r in rows:
            self._upsert(
                "manual_imports",
                {"kind": kind, "series": series, "date": r["date"], "value": r["value"],
                 "source": "manual", "as_of": r["date"],
                 "available_at": r.get("available_at", r["date"]), "collected_at": now,
                 "event": r.get("event"), "impact": r.get("impact")},
                ["kind", "series", "date"],
            )
            n += 1
        return n

    def manual(self, kind: str, series: str, as_of: str, limit: int = 60) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM manual_imports WHERE kind=? AND series=? AND as_of<=? "
            "AND available_at<=? ORDER BY as_of DESC LIMIT ?",
            (kind, series, as_of, as_of, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def manual_kind(self, kind: str, as_of: str, limit: int = 60) -> list[dict]:
        """All rows of a kind across series (ETF flows arrive as SPDR/IAU/…)."""
        rows = self._conn.execute(
            "SELECT * FROM manual_imports WHERE kind=? AND as_of<=? "
            "AND available_at<=? ORDER BY as_of DESC, series LIMIT ?",
            (kind, as_of, as_of, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def calendar_upcoming(self, as_of: str, limit: int = 30) -> list[dict]:
        """Future events KNOWN at `as_of` — calendar rows carry as_of = event
        date (future), so the no-look-ahead as_of<=T filter does not apply;
        the knowledge constraint is available_at (import time) only (D5/D13)."""
        rows = self._conn.execute(
            "SELECT * FROM manual_imports WHERE kind='calendar' AND available_at<=? "
            "ORDER BY as_of ASC LIMIT ?",
            (as_of, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- bias snapshots / reports -------------------------------------------------
    def save_snapshot(self, kind: str, as_of: str, payload: dict, config_json: str,
                      config_hash: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO snapshots (created_at, as_of, kind, score, label, reliability,"
            " payload, config_json, config_hash) VALUES (?,?,?,?,?,?,?,?,?)",
            (utciso(), as_of, kind, payload.get("score"), payload.get("label"),
             payload.get("reliability"), json_dumps(payload), config_json, config_hash),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def snapshots(self, kind: str | None = None, limit: int = 50) -> list[dict]:
        q = "SELECT * FROM snapshots"
        args: list = []
        if kind:
            q += " WHERE kind=?"
            args.append(kind)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self._conn.execute(q, args).fetchall()]

    def get_snapshot(self, snapshot_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return dict(row) if row else None

    def last_snapshot_age_days(self, kind: str, now: datetime | None = None) -> float | None:
        row = self._conn.execute(
            "SELECT created_at FROM snapshots WHERE kind=? ORDER BY id DESC LIMIT 1",
            (kind,),
        ).fetchone()
        if not row:
            return None
        created = datetime.fromisoformat(row["created_at"])
        now = now or utcnow()
        return (now - created).total_seconds() / 86400.0

    def save_report(self, kind: str, as_of: str, text: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO reports (created_at, as_of, kind, text) VALUES (?,?,?,?)",
            (utciso(), as_of, kind, text),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def reports(self, kind: str | None = None, limit: int = 20) -> list[dict]:
        q = "SELECT * FROM reports"
        args: list = []
        if kind:
            q += " WHERE kind=?"
            args.append(kind)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        return [dict(r) for r in self._conn.execute(q, args).fetchall()]

    def last_available(self, table: str, as_of: str) -> str | None:
        """Most recent as_of present in a table (for freshness computation)."""
        date_col = "as_of"
        row = self._conn.execute(
            f"SELECT MAX({date_col}) AS m FROM {table} WHERE {date_col}<=?", (as_of,)
        ).fetchone()
        return row["m"] if row and row["m"] else None


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, sort_keys=True, default=str)
