"""Millisecond-ISO timestamps matching the actor's output shape."""

from __future__ import annotations

from datetime import UTC, datetime


def epoch_to_iso(seconds: int | None) -> str | None:
    """Convert a Unix-seconds timestamp to ``YYYY-MM-DDTHH:MM:SS.000Z``."""
    if not seconds:
        return None
    stamp = datetime.fromtimestamp(seconds, tz=UTC)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def now_iso() -> str:
    """Current UTC time in the millisecond-ISO output shape."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
