"""How far a license has got towards Business Solo, read back from the license.

Steps a and c write their marks in the request that does the step, the move
shows in the license's policy, and the notice's mark follows its mail. So a run
that stopped is finished by the next, and a finished license is left alone.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from license.jobs import jobs_metadata
from license.models import (
    META_CONVERSION_NOTICE_SENT_ON,
    META_CONVERTED_FROM,
    META_CONVERTED_ON,
    META_EXPIRY_BEFORE_CONVERSION,
    META_JOBS,
    META_MOVED_TO_BUSINESS_ON,
    META_PLAN,
    META_SUBSCRIPTION,
    LicenseRecord,
)

INDIVIDUAL = "individual"
# Recorded for a license that had no expiry, so that cannot read as one never recorded.
NO_EXPIRY = "none"


def started(record: LicenseRecord) -> bool:
    """Step a is done: the conversion marks are written."""
    return record.metadata.get(META_CONVERTED_FROM) == INDIVIDUAL


def moved(record: LicenseRecord) -> bool:
    """Steps b and c are done: on the Business policy, and Business Solo."""
    return bool(record.metadata.get(META_MOVED_TO_BUSINESS_ON))


def notice_sent_on(record: LicenseRecord) -> str | None:
    """Step d is done: the day its conversion notice was sent."""
    return str(record.metadata.get(META_CONVERSION_NOTICE_SENT_ON) or "") or None


def half_converted(record: LicenseRecord) -> bool:
    """A run started it and none has finished it."""
    return started(record) and notice_sent_on(record) is None


def conversion_marks(
    record: LicenseRecord, *, subscription_id: str | None, today: date
) -> dict[str, str]:
    """Step a: the marks alone, so a license Keygen refuses to move stays Individual.

    Every other key is kept.
    """
    metadata = dict(record.metadata)
    metadata.update(
        {
            META_CONVERTED_FROM: INDIVIDUAL,
            META_CONVERTED_ON: today.isoformat(),
            META_EXPIRY_BEFORE_CONVERSION: record.expiry or NO_EXPIRY,
        }
    )
    if subscription_id and not metadata.get(META_SUBSCRIPTION):
        # Every Business license carries it: a seat change finds the license by it alone.
        metadata[META_SUBSCRIPTION] = subscription_id
    return metadata


def business_metadata(record: LicenseRecord, *, today: date) -> dict[str, str]:
    """Step c, once on the Business policy: Business's plan and jobs, and the mark."""
    return {
        **record.metadata,
        META_PLAN: "business",
        META_JOBS: jobs_metadata(),
        META_MOVED_TO_BUSINESS_ON: today.isoformat(),
    }


def marked(record: LicenseRecord, key: str, today: date) -> dict[str, str]:
    """The license's metadata with one step's mark added; Keygen replaces it whole."""
    return {**record.metadata, key: today.isoformat()}


def instant(value: str | None) -> datetime | None:
    """A Keygen time, read as UTC when it names no zone."""
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
