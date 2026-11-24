"""`invoice.paid`: the period paid for extends the same license, and a renewal is mailed.

The same key renews (ADR 0080), so nothing new is minted: the license's expiry
moves to the end of the paid period plus the grace. The expiry is read from the
live subscription, which makes a retried or late event set the same value. Only
a period's invoice moves it: a proration for people moves only their count.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from license import keygen
from license.email.deliver import deliver_licenses
from license.email.message import BusinessCopy
from license.models import META_PLAN
from license.records import issued_for_id

from .paid_period import (
    PERIOD_BILLING_REASONS,
    expiry_for,
    people,
    retrieve,
    stripe_id,
    subscription_of_invoice,
)
from .subscribed_license import license_for_subscription, with_subscription

logger = logging.getLogger(__name__)


async def renew_from_invoice(invoice: Any, *, stripe_client: Any) -> None:
    """Extend the license a paid subscription invoice is for; raises so Stripe retries."""
    subscription_id = subscription_of_invoice(invoice)
    if not subscription_id:
        return
    invoice_id = stripe_id(invoice)
    reason = getattr(invoice, "billing_reason", None)

    found = await license_for_subscription(subscription_id, stripe_client)
    if found is None:
        if reason == "subscription_create":
            # The checkout's own event mints it, with this period's expiry.
            logger.info(
                "Invoice %s starts subscription %s before its license exists",
                invoice_id,
                subscription_id,
            )
        else:
            logger.warning(
                "Paid invoice %s renews subscription %s, which no license carries",
                invoice_id,
                subscription_id,
            )
        return

    subscription = await retrieve(stripe_client, subscription_id)
    record = found.record
    changes: dict[str, Any] = {}

    # A proration pays no period, and the live one may be a year not yet paid.
    expiry = expiry_for(subscription) if reason in PERIOD_BILLING_REASONS else None
    current = _instant(record.expiry)
    if expiry is not None and (current is None or expiry > current):
        changes["expiry"] = expiry
    # The firm confirms its people at renewal; a missed seat change heals here too.
    count = people(subscription)
    if (
        record.metadata.get(META_PLAN) == "business"
        and count
        and count != record.max_users
    ):
        changes["max_users"] = count
    if not found.recorded:
        changes["metadata"] = with_subscription(record, subscription_id)
    if not changes:
        return

    await keygen.update_license(record.keygen_license_id, **changes)
    logger.info(
        "Invoice %s updated license %s: %s",
        invoice_id,
        record.keygen_license_id,
        ", ".join(sorted(changes)),
    )
    if "expiry" in changes and reason == "subscription_cycle":
        await _mail_renewed(record.keygen_license_id, invoice_id)


async def _mail_renewed(license_id: str, invoice_id: str | None) -> None:
    """Best effort, like the purchase mail: the app fetches the file when online anyway."""
    try:
        issued = await issued_for_id(license_id)
        if issued is None:
            logger.warning(
                "License %s renewed but is not in good standing; not mailing it",
                license_id,
            )
            return
        await deliver_licenses(
            "renewal",
            to=issued.email,
            certificates=[issued.certificate],
            business=BusinessCopy.of(issued),
            idempotency_key=invoice_id,
        )
    except Exception:
        logger.warning(
            "Renewed license %s but could not email it", license_id, exc_info=True
        )


def _instant(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
