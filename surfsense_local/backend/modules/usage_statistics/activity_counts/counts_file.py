"""The counts file: one small JSON object in the data folder, rewritten whole on each count.

Keyed by UTC hour, so a 7-day window is right to the hour; 40 days covers any
window the weekly report asks for with room to spare.
"""

import json
import logging
import os
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

FILE_NAME = "usage-counts.json"
KEEP = timedelta(days=40)
_HOUR = "%Y-%m-%dT%H"
_lock = threading.Lock()


class Activity(StrEnum):
    AGENT_TURN = "agent_turns"
    PLUGIN_CALL = "plugin_calls"
    LOCAL_ANSWER = "local_answers"
    REMOTE_ANSWER = "remote_answers"


# Counted only once a reply has text, so these alone mark a model as having answered.
_ANSWERS = (Activity.LOCAL_ANSWER, Activity.REMOTE_ANSWER)


@dataclass(frozen=True)
class ActivityCounts:
    # None when counting began before this library had any chat: nothing was missed.
    counted_since: datetime | None
    # Whether a model ever answered with text; outlives the pruned hours.
    answered: bool
    hours: Mapping[str, Mapping[str, int]]

    def covers(self, since: datetime) -> bool:
        """Whether every count since `since` is here, rather than some before counting began."""
        return self.counted_since is None or self.counted_since <= since

    def total(self, activity: Activity, since: datetime) -> int:
        first = since.astimezone(UTC).strftime(_HOUR)
        return sum(
            counts.get(activity, 0)
            for hour, counts in self.hours.items()
            if hour >= first
        )


def counts_path() -> Path:
    return get_storage_settings().data_dir / FILE_NAME


def read_counts() -> ActivityCounts | None:
    """None when there is no readable file: then nothing can be said."""
    raw = _read_raw()
    if raw is None:
        return None
    since = raw.get("counted_since")
    try:
        counted_since = None if since is None else datetime.fromisoformat(since)
    except (TypeError, ValueError):
        return None
    hours = raw.get("hours")
    return ActivityCounts(
        counted_since=counted_since,
        answered=bool(raw.get("answered")),
        hours=hours if isinstance(hours, dict) else {},
    )


def start_counting(had_chats: bool, now: datetime | None = None) -> None:
    """Create the file at startup if it is missing. A library with chats already
    has turns nobody counted, so its counts start now; an empty one misses nothing."""
    try:
        with _lock:
            if _read_raw() is not None:
                return
            started = None if not had_chats else _now(now).isoformat()
            _write({"counted_since": started, "answered": False, "hours": {}})
    except OSError:
        logger.warning("could not start the usage counts", exc_info=True)


def add(counts: Mapping[Activity, int], now: datetime | None = None) -> None:
    """Best effort: a count that cannot be written is lost, never the turn it counts."""
    if not any(counts.values()):
        return
    at = _now(now)
    try:
        with _lock:
            raw = _read_raw() or {
                "counted_since": at.isoformat(),
                "answered": False,
                "hours": {},
            }
            hours: dict[str, dict[str, int]] = raw.setdefault("hours", {})
            hour = hours.setdefault(at.strftime(_HOUR), {})
            for activity, amount in counts.items():
                hour[activity] = hour.get(activity, 0) + amount
            if any(counts.get(activity) for activity in _ANSWERS):
                raw["answered"] = True
            oldest = (at - KEEP).strftime(_HOUR)
            raw["hours"] = {key: value for key, value in hours.items() if key >= oldest}
            _write(raw)
    except OSError:
        logger.warning("could not write the usage counts", exc_info=True)


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(UTC)


def _read_raw() -> dict[str, Any] | None:
    try:
        raw = json.loads(counts_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _write(raw: dict[str, Any]) -> None:
    path = counts_path()
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(raw, separators=(",", ":")), encoding="utf-8")
    os.replace(partial, path)
