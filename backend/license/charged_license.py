"""The one license a Stripe payment paid for, for a refund or a dispute.

A subscription's charge belongs to an invoice, not to a checkout session, so it
is traced invoice -> subscription -> license. A one-time payment is traced to
its checkout session; it often has no Stripe customer at all, since a Payment
Link's default `customer_creation` makes none.
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

import anyio

from license.models import LicenseNotFoundError
from license.records import find_license_by_checkout_session
from license.subscription.paid_period import (
    PERIOD_BILLING_REASONS,
    stripe_id,
    subscription_of_invoice,
)
from license.subscription.subscribed_license import license_for_subscription

logger = logging.getLogger(__name__)


async def license_paid_by(payment_intent: Any, stripe_client: Any) -> str | None:
    """The license id, or ``None`` when the payment traces to no single license.

    A payment for added people is not the license's price, so it traces to
    none: taking the whole license away over it would be a wrong suspension,
    and those are silent to the customer.
    """
    payment_intent_id = stripe_id(payment_intent)
    if not payment_intent_id or stripe_client is None:
        return None

    invoice = await _invoice_paid_by(payment_intent_id, stripe_client)
    subscription_id = subscription_of_invoice(invoice) if invoice is not None else None
    if subscription_id:
        reason = getattr(invoice, "billing_reason", None)
        if reason not in PERIOD_BILLING_REASONS:
            logger.warning(
                "Payment %s paid invoice %s (%s), not a period; tracing no license",
                payment_intent_id,
                stripe_id(invoice),
                reason,
            )
            return None
        found = await license_for_subscription(subscription_id, stripe_client)
        return found.record.keygen_license_id if found else None

    # In a thread: the event loop also streams every plugin call.
    sessions = await anyio.to_thread.run_sync(
        partial(
            stripe_client.v1.checkout.sessions.list,
            params={"payment_intent": payment_intent_id, "limit": 1},
        )
    )
    if not sessions.data:
        return None
    try:
        record = await find_license_by_checkout_session(sessions.data[0].id)
    except LicenseNotFoundError:
        return None
    return record.keygen_license_id or None


async def _invoice_paid_by(payment_intent_id: str, stripe_client: Any) -> Any:
    """The invoice a payment settled; since API 2025-03-31 a charge no longer names it."""
    payments = await anyio.to_thread.run_sync(
        partial(
            stripe_client.v1.invoice_payments.list,
            params={
                "payment": {
                    "type": "payment_intent",
                    "payment_intent": payment_intent_id,
                },
                "limit": 1,
                "expand": ["data.invoice"],
            },
        )
    )
    if not payments.data:
        return None
    invoice = payments.data[0].invoice
    if isinstance(invoice, str):
        invoice = await anyio.to_thread.run_sync(
            stripe_client.v1.invoices.retrieve, invoice
        )
    return invoice
