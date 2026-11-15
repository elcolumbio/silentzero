"""An append-only run log, because one observation cannot tell nothing from broken.

A single zero is ambiguous by construction. What makes it legible is its own past:
a board that returned 40 postings on every run for six months and returns 0 today is
broken; a board that has returned 0 since the day it was added is empty. The gates
cannot know that. The ledger can.

SQLite, append-only. Rows are never rewritten; a run is closed by setting its
``finished_at`` once, and nothing else in the store is ever updated.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from .result import Reading, State

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL DEFAULT '',
    started_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS readings (
    run_id  INTEGER NOT NULL REFERENCES runs(run_id),
    source  TEXT    NOT NULL,
    state   TEXT    NOT NULL,
    count   INTEGER NOT NULL,
    at      TEXT    NOT NULL,
    because TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS readings_source ON readings(source, run_id);
"""


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse(s: str) -> datetime:
    return datetime.fromisoformat(s)


class Ledger:
    """The run log. ``Ledger(":memory:")`` is fine for tests and for a dry run."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA busy_timeout=30000")
        if self.path != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._db.commit()

    # -- writing ---------------------------------------------------------

    def start_run(self, label: str = "") -> int:
        cur = self._db.execute(
            "INSERT INTO runs (label, started_at) VALUES (?, ?)",
            (label, _iso(datetime.now(timezone.utc))),
        )
        self._db.commit()
        return int(cur.lastrowid)

    def record(self, run_id: int, reading: Reading | Iterable[Reading]) -> None:
        rows = [reading] if isinstance(reading, Reading) else list(reading)
        self._db.executemany(
            "INSERT INTO readings (run_id, source, state, count, at, because) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(run_id, r.source, r.state.value, r.count, _iso(r.at), r.because) for r in rows],
        )
        self._db.commit()

    def finish_run(self, run_id: int) -> None:
        self._db.execute(
            "UPDATE runs SET finished_at = ? WHERE run_id = ? AND finished_at IS NULL",
            (_iso(datetime.now(timezone.utc)), run_id),
        )
        self._db.commit()

    # -- reading ---------------------------------------------------------

    def readings(self, run_id: int) -> list[Reading]:
        rows = self._db.execute(
            "SELECT * FROM readings WHERE run_id = ? ORDER BY rowid", (run_id,)
        ).fetchall()
        return [self._reading(r) for r in rows]

    def history(self, source: str, *, limit: int = 50, before_run: int | None = None) -> list[Reading]:
        """Most recent first."""
        sql = "SELECT * FROM readings WHERE source = ?"
        args: list[object] = [source]
        if before_run is not None:
            sql += " AND run_id < ?"
            args.append(before_run)
        sql += " ORDER BY run_id DESC, rowid DESC LIMIT ?"
        args.append(limit)
        return [self._reading(r) for r in self._db.execute(sql, args).fetchall()]

    def last_found(self, source: str, *, before_run: int | None = None) -> Reading | None:
        """The most recent run in which this source actually produced rows.

        This is the fact that makes a zero legible. ``None`` means the source has
        never produced anything, and a zero from it today says nothing new.
        """
        sql = "SELECT * FROM readings WHERE source = ? AND state = 'found'"
        args: list[object] = [source]
        if before_run is not None:
            sql += " AND run_id < ?"
            args.append(before_run)
        sql += " ORDER BY run_id DESC, rowid DESC LIMIT 1"
        row = self._db.execute(sql, args).fetchone()
        return self._reading(row) if row else None

    def sources(self) -> list[str]:
        return [r[0] for r in self._db.execute(
            "SELECT DISTINCT source FROM readings ORDER BY source")]

    def runs(self, limit: int = 20) -> list[sqlite3.Row]:
        return self._db.execute(
            "SELECT * FROM runs ORDER BY run_id DESC LIMIT ?", (limit,)
        ).fetchall()

    def last_run(self) -> int | None:
        row = self._db.execute("SELECT MAX(run_id) AS r FROM runs").fetchone()
        return int(row["r"]) if row and row["r"] is not None else None

    # -- plumbing --------------------------------------------------------

    @staticmethod
    def _reading(row: sqlite3.Row) -> Reading:
        return Reading(
            source=row["source"],
            state=State(row["state"]),
            count=int(row["count"]),
            at=_parse(row["at"]),
            because=row["because"] or "",
        )

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def record_run(ledger: Ledger, readings: Sequence[Reading], *, label: str = "") -> int:
    """Write a whole run in one call and close it. Returns the run id."""
    run_id = ledger.start_run(label)
    ledger.record(run_id, readings)
    ledger.finish_run(run_id)
    return run_id
