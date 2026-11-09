"""The meter's records in one SQLite file: calls per day, license, plugin, tool and outcome."""

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path

from host.usage_meter.call_counts import UNLICENSED, CallKey, Tally

# How long a write waits on another process holding the file, as the rollup command does.
BUSY_SECONDS = 10.0

_SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS plugin_calls (
    day TEXT NOT NULL,
    license TEXT NOT NULL,
    plugin TEXT NOT NULL,
    tool TEXT NOT NULL,
    outcome TEXT NOT NULL,
    calls INTEGER NOT NULL,
    total_ms INTEGER NOT NULL,
    PRIMARY KEY (day, license, plugin, tool, outcome)
);
CREATE TABLE IF NOT EXISTS license_first_seen (
    license TEXT PRIMARY KEY,
    first_day TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rollups_sent (day TEXT PRIMARY KEY);
"""

_ADD_CALLS = """
INSERT INTO plugin_calls VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (day, license, plugin, tool, outcome) DO UPDATE SET
    calls = calls + excluded.calls,
    total_ms = total_ms + excluded.total_ms
"""

_ADD_FIRST_SEEN = """
INSERT INTO license_first_seen VALUES (?, ?)
ON CONFLICT (license) DO UPDATE SET first_day = min(first_day, excluded.first_day)
"""

# The field names are the rollup's and the admin route's.
_TOOL_USAGE = """
SELECT plugin, tool, outcome, sum(calls), sum(total_ms),
       count(DISTINCT CASE WHEN license != :unlicensed THEN license END)
FROM plugin_calls WHERE day = :day
GROUP BY plugin, tool, outcome ORDER BY plugin, tool, outcome
"""


@dataclass(frozen=True)
class ToolUsage:
    plugin: str
    tool: str
    outcome: str
    calls: int
    total_ms: int
    distinct_licences: int


@dataclass(frozen=True)
class DailyUsage:
    """One day's usage with no license id in it: all that leaves the host."""

    day: str
    tools: list[ToolUsage]
    active_licences: int
    new_licences: int


class UsageStore:
    """Blocking, so the meter calls it from a worker thread; each call opens its own connection."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._ready = False

    def add(self, counts: Mapping[CallKey, Tally]) -> None:
        with self._connected() as db:
            db.executemany(
                _ADD_CALLS,
                [
                    (k.day, k.license, k.plugin, k.tool, k.outcome, t.calls, t.total_ms)
                    for k, t in counts.items()
                ],
            )
            db.executemany(
                _ADD_FIRST_SEEN,
                [(k.license, k.day) for k in counts if k.license != UNLICENSED],
            )

    def daily_usage(self, day: str) -> DailyUsage:
        with self._connected() as db:
            rows = db.execute(_TOOL_USAGE, {"day": day, "unlicensed": UNLICENSED})
            tools = [ToolUsage(*row) for row in rows]
            (active,) = db.execute(
                "SELECT count(DISTINCT license) FROM plugin_calls"
                " WHERE day = ? AND license != ?",
                (day, UNLICENSED),
            ).fetchone()
            (new,) = db.execute(
                "SELECT count(*) FROM license_first_seen WHERE first_day = ?", (day,)
            ).fetchone()
        return DailyUsage(day, tools, active, new)

    def first_seen(self) -> dict[str, str]:
        with self._connected() as db:
            rows = db.execute("SELECT license, first_day FROM license_first_seen")
            return dict(rows.fetchall())

    def forget_before(self, day: str) -> None:
        """Rows from before `day`, and the first day of each license left with none."""
        with self._connected() as db:
            db.execute("DELETE FROM plugin_calls WHERE day < ?", (day,))
            db.execute(
                "DELETE FROM license_first_seen"
                " WHERE license NOT IN (SELECT license FROM plugin_calls)"
            )

    def rollup_sent(self, day: str) -> bool:
        with self._connected() as db:
            sent = db.execute("SELECT 1 FROM rollups_sent WHERE day = ?", (day,))
            return sent.fetchone() is not None

    def mark_rollup_sent(self, day: str) -> None:
        with self._connected() as db:
            db.execute("INSERT OR IGNORE INTO rollups_sent VALUES (?)", (day,))

    @contextmanager
    def _connected(self) -> Iterator[sqlite3.Connection]:
        """One transaction, committed when the block ends."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=BUSY_SECONDS)) as db:
            if not self._ready:
                db.executescript(_SCHEMA)
                self._ready = True
            with db:
                yield db
