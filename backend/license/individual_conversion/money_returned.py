"""Whether a license's purchase went back to its buyer: a payment refunded in full, or disputed.

The webhook suspends such a license, but the server before the switch release
traces no refund of a subscription's charge and handles no dispute (ADR 0080),
so a buyer refunded then can still hold an active license. Read-only.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import partial
from typing import Any

import anyio

from license.subscription.paid_period import stripe_id


async def period_payment_returned(
    period_invoices: Iterable[Any], stripe_client: Any
) -> bool:
    """Any payment of the invoices that bought its periods, the ones the webhook suspends for."""
    for invoice in period_invoices:
        payments = await _listed(
            stripe_client.v1.invoice_payments.list,
            {"invoice": stripe_id(invoice), "status": "paid", "limit": 100},
        )
        for payment in payments:
            if await _returned(getattr(payment, "payment", None), stripe_client):
                return True
    return False


async def payment_intent_returned(payment_intent: Any, stripe_client: Any) -> bool:
    """A payment made once, such as a checkout's in payment mode."""
    intent = stripe_id(payment_intent)
    if intent is None:
        return False
    charges = await _listed(
        stripe_client.v1.charges.list, {"payment_intent": intent, "limit": 100}
    )
    return any(_given_back(charge) for charge in charges)


async def _returned(payment: Any, stripe_client: Any) -> bool:
    kind = getattr(payment, "type", None)
    if kind == "payment_intent":
        return await payment_intent_returned(
            getattr(payment, "payment_intent", None), stripe_client
        )
    charge_id = stripe_id(getattr(payment, "charge", None))
    if kind != "charge" or charge_id is None:
        return False
    charge = await anyio.to_thread.run_sync(
        stripe_client.v1.charges.retrieve, charge_id
    )
    return _given_back(charge)


def _given_back(charge: Any) -> bool:
    """Disputed, or refunded in full as the webhook reads a refund; a partial one is not."""
    if getattr(charge, "disputed", False) or getattr(charge, "refunded", False):
        return True
    amount = getattr(charge, "amount", None)
    refunded = getattr(charge, "amount_refunded", None)
    return (
        isinstance(amount, int)
        and isinstance(refunded, int)
        and amount > 0
        and refunded >= amount
    )


async def _listed(list_some: Any, params: dict[str, Any]) -> list[Any]:
    # In a thread, as every Stripe call in the backend.
    page = await anyio.to_thread.run_sync(partial(list_some, params=params))
    return list(getattr(page, "data", None) or [])
