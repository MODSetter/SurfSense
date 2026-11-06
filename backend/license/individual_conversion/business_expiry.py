"""The expiry a license gets as Business Solo: what its paid period buys Business, never less.

Business ends 30 days after the period paid for (``paid_period.GRACE``); an
Individual license minted before that rule ends with its period, or never. Only
ever later, as a renewal moves it, so a renewal or a correction made since the
license was listed is never cut.
"""

from __future__ import annotations

from datetime import datetime

from license.models import LicenseRecord

from .live_subscription import LiveSubscription
from .progress import instant


def business_expiry(
    record: LicenseRecord, subscription: LiveSubscription
) -> datetime | None:
    """The expiry to write, or ``None`` to keep the license's own."""
    paid_through = subscription.paid_through
    if paid_through is None:
        return None
    current = instant(record.expiry)
    if current is not None and current >= paid_through:
        return None
    return paid_through


def expiry_once_converted(
    record: LicenseRecord, subscription: LiveSubscription
) -> datetime | None:
    """When the license ends as Business Solo; ``None`` when it never does."""
    return business_expiry(record, subscription) or instant(record.expiry)
