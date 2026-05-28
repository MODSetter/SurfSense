"""Lock the cron + timezone + UTC normalization contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.automations.triggers.schedule.cron import (
    InvalidCronError,
    compute_next_fire_at,
    validate_cron,
)

pytestmark = pytest.mark.unit


def test_compute_next_fire_at_returns_next_match_normalized_to_utc() -> None:
    """``compute_next_fire_at`` evaluates the cron in the given IANA timezone
    and returns the next strictly-later match expressed in UTC.

    Setup: ``0 9 * * 1-5`` (09:00 Monday-Friday) in ``Africa/Kigali``
    (UTC+2, no DST). With ``after`` = Tuesday 05:00 UTC (= 07:00 local),
    the next fire is the same Tuesday at 09:00 local = 07:00 UTC.
    """
    after = datetime(2026, 5, 26, 5, 0, tzinfo=UTC)  # Tue 07:00 Kigali

    next_fire = compute_next_fire_at("0 9 * * 1-5", "Africa/Kigali", after=after)

    assert next_fire == datetime(2026, 5, 26, 7, 0, tzinfo=UTC)


def test_compute_next_fire_at_respects_dst_offset_change() -> None:
    """A daily cron in a DST-observing tz fires at the same local hour
    across the DST boundary, which produces a different UTC offset on
    either side of the transition.

    Setup: ``0 9 * * *`` (09:00 every day) in ``America/New_York``.
    NY is UTC-5 in winter (EST), UTC-4 in summer (EDT). Evaluating from
    each side of the spring-forward in 2026 (Sun Mar 8 at 02:00 → 03:00):

    - winter: ``after`` = 2026-02-15 (EST, UTC-5) → next 09:00 EST = 14:00 UTC
    - summer: ``after`` = 2026-04-15 (EDT, UTC-4) → next 09:00 EDT = 13:00 UTC
    """
    winter_after = datetime(2026, 2, 15, 0, 0, tzinfo=UTC)
    summer_after = datetime(2026, 4, 15, 0, 0, tzinfo=UTC)

    winter_fire = compute_next_fire_at("0 9 * * *", "America/New_York", after=winter_after)
    summer_fire = compute_next_fire_at("0 9 * * *", "America/New_York", after=summer_after)

    assert winter_fire == datetime(2026, 2, 15, 14, 0, tzinfo=UTC)
    assert summer_fire == datetime(2026, 4, 15, 13, 0, tzinfo=UTC)


def test_compute_next_fire_at_is_strictly_after_when_after_equals_a_match() -> None:
    """When ``after`` lands exactly on a cron match, the result jumps to the
    next match — never the same instant. Required so the schedule-tick
    can pass ``next_fire_at`` itself as ``after`` to advance to the
    following slot without double-firing.

    Setup: weekday 09:00 Kigali. ``after`` = Mon 09:00 Kigali = 07:00 UTC
    (an exact match) → next fire must be Tue 09:00 Kigali = next day 07:00 UTC.
    """
    after = datetime(2026, 5, 25, 7, 0, tzinfo=UTC)  # Mon 09:00 Kigali — exact match

    next_fire = compute_next_fire_at("0 9 * * 1-5", "Africa/Kigali", after=after)

    assert next_fire == datetime(2026, 5, 26, 7, 0, tzinfo=UTC)  # Tue 09:00 Kigali


def test_validate_cron_rejects_malformed_cron_expression() -> None:
    """A syntactically invalid cron must be rejected at validation time so
    bad triggers can't reach storage and explode at fire time."""
    with pytest.raises(InvalidCronError):
        validate_cron("this is not cron", "UTC")


def test_validate_cron_rejects_unknown_timezone() -> None:
    """A non-IANA timezone string must be rejected at validation time —
    the same protective gate as the cron expression itself."""
    with pytest.raises(InvalidCronError):
        validate_cron("0 9 * * *", "Mars/Olympus_Mons")
