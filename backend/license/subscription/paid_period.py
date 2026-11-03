"""What a subscription has paid for: the expiry it buys, and its people."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import anyio

# A lapsed license stops new job runs 30 days after it lapses (ADR 0079), and
# the same days cover Stripe's retries of a failed renewal.
GRACE = timedelta(days=30)

# The invoices that pay for a period. A `subscription_update` invoice is the
# proration for people added mid-year: it neither renews nor, refunded,
# takes the license away.
PERIOD_BILLING_REASONS = frozenset({"subscription_create", "subscription_cycle"})


def _field(obj: Any, name: str) -> Any:
    """A Stripe object's field; a ``StripeObject`` is no dict in stripe>=15."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def stripe_id(value: Any) -> str | None:
    """An expandable field's id, whether Stripe sent the id or the object."""
    if isinstance(value, str):
        return value or None
    return str(_field(value, "id") or "") or None


def subscription_of_invoice(invoice: Any) -> str | None:
    """The subscription an invoice bills: under ``parent`` since API 2025-03-31, else top level."""
    details = _field(_field(invoice, "parent"), "subscription_details")
    return stripe_id(_field(details, "subscription")) or stripe_id(
        _field(invoice, "subscription")
    )


def items_of(subscription: Any) -> list[Any]:
    return list(_field(_field(subscription, "items"), "data") or [])


def period_end(subscription: Any) -> datetime | None:
    """When the period paid for ends: on the items since API 2025-03-31, else on the subscription."""
    ends = [
        end
        for end in (
            _field(item, "current_period_end") for item in items_of(subscription)
        )
        if isinstance(end, int)
    ]
    legacy = _field(subscription, "current_period_end")
    if not ends and isinstance(legacy, int):
        ends = [legacy]
    return datetime.fromtimestamp(max(ends), UTC) if ends else None


def expiry_for(subscription: Any) -> datetime | None:
    """The license expiry the paid period buys: its end plus the grace."""
    end = period_end(subscription)
    return end + GRACE if end else None


def people(subscription: Any) -> int | None:
    """How many people the subscription pays for: its one price's quantity."""
    quantities = [
        quantity
        for quantity in (_field(item, "quantity") for item in items_of(subscription))
        if isinstance(quantity, int)
    ]
    return sum(quantities) if quantities else None


async def retrieve(stripe_client: Any, subscription_id: str) -> Any:
    # In a thread: the event loop also streams every plugin call.
    return await anyio.to_thread.run_sync(
        partial(stripe_client.v1.subscriptions.retrieve, subscription_id)
    )
