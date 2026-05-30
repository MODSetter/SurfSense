"""Cron math for the ``schedule`` trigger: validate + advance ``next_fire_at``."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter


class InvalidCronError(ValueError):
    """Raised when a cron expression or timezone fails validation."""


def validate_cron(cron: str, timezone: str) -> None:
    """Raise ``InvalidCronError`` if cron or timezone are unusable."""
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise InvalidCronError(f"unknown timezone {timezone!r}") from exc

    try:
        croniter(cron)
    except (CroniterBadCronError, ValueError) as exc:
        raise InvalidCronError(f"invalid cron {cron!r}: {exc}") from exc


def compute_next_fire_at(cron: str, timezone: str, *, after: datetime) -> datetime:
    """Return the next moment matching ``cron`` in ``timezone`` strictly after ``after``.

    The result is normalized to UTC for storage. ``after`` is converted into the
    given timezone before evaluation so DST and IANA rules apply correctly.
    """
    tz = ZoneInfo(timezone)
    base = (
        after.astimezone(tz)
        if after.tzinfo
        else after.replace(tzinfo=UTC).astimezone(tz)
    )
    nxt: datetime = croniter(cron, base).get_next(datetime)
    return nxt.astimezone(UTC)
