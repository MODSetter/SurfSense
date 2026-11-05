"""`customer.subscription.updated`: a Business license follows its subscription's people.

Only the count moves here. The period can advance in this event before the
renewal is paid, so the expiry waits for `invoice.paid`.
"""

from __future__ import annotations

import logging
from typing import Any

from license import keygen
from license.models import META_PLAN

from .paid_period import people, stripe_id
from .subscribed_license import license_for_subscription

logger = logging.getLogger(__name__)


async def follow_people(subscription: Any) -> None:
    """Set the license's ``maxUsers`` to the subscription's quantity; raises so Stripe retries."""
    subscription_id = stripe_id(subscription)
    if not subscription_id:
        return
    # Every Business license was sold with the id written, so no Stripe lookup.
    found = await license_for_subscription(
        subscription_id, None, through_checkout=False
    )
    if found is None or found.record.metadata.get(META_PLAN) != "business":
        return
    count = people(subscription)
    if not count or count == found.record.max_users:
        return
    await keygen.update_license(found.record.keygen_license_id, max_users=count)
    logger.info(
        "License %s now covers %d people (subscription %s)",
        found.record.keygen_license_id,
        count,
        subscription_id,
    )
