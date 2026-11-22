"""`customer.subscription.deleted`: the license is left to lapse, never suspended.

Its expiry already ends the last period paid for plus the grace, and with no
more paid invoices nothing extends it. Suspension is for money returned.
"""

from __future__ import annotations

import logging
from typing import Any

from .paid_period import stripe_id
from .subscribed_license import license_for_subscription

logger = logging.getLogger(__name__)


async def let_lapse(subscription: Any) -> None:
    """Change nothing in Keygen; tell support when the license will lapse."""
    subscription_id = stripe_id(subscription)
    if not subscription_id:
        return
    found = await license_for_subscription(
        subscription_id, None, through_checkout=False
    )
    if found is None:
        logger.info("Subscription %s ended; no license carries it", subscription_id)
        return
    logger.info(
        "Subscription %s ended; license %s is not renewed and lapses at %s",
        subscription_id,
        found.record.keygen_license_id,
        found.record.expiry,
    )
