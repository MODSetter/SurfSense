"""The Stripe purchase behind a license: whether it renews, has settled not to, and what it paid for.

The conversion notice says which, so only Stripe's answer lets a license
convert. One sold before ``stripeSubscriptionId`` was written is traced through
the checkout session that started its subscription, as renewals trace it.
Read-only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from typing import Any

import anyio
import stripe

from license.checkout import subscription_id as subscription_of_checkout
from license.models import META_SESSION, META_SUBSCRIPTION, PAID_STATUSES
from license.subscription.paid_period import (
    GRACE,
    PERIOD_BILLING_REASONS,
    people,
    period_end,
)

from .money_returned import payment_intent_returned, period_payment_returned
from .renewal_price import renews_above_price_paid

# Not past_due: Stripe is retrying a failed renewal, which may yet renew or end.
_RENEWING_STATUSES = frozenset({"active", "trialing"})
# The discounts on the subscription and on its item, which decide its renewal price.
_EXPAND = ["discounts", "items.data.discounts"]


@dataclass(frozen=True, slots=True)
class LiveSubscription:
    # None for a purchase paid once, with no subscription.
    id: str | None = None
    status: str | None = None
    # Set to end, at its period's end or on a date within it.
    cancelling: bool = False
    # A cancel date past the period paid for: Stripe renews once more, prorated, first.
    cancels_on: datetime | None = None
    # When the period paid for ends: the day it renews, if it does.
    period_end: datetime | None = None
    # The expiry its paid period buys a Business license: the period's end plus the grace.
    paid_through: datetime | None = None
    people: int | None = None
    # A payment for it was refunded in full or disputed.
    returned: bool = False
    # The year paid for was discounted and no discount lasts into its renewals.
    renews_above_price_paid: bool = False
    # Why Stripe holds no purchase for it.
    missing: str | None = None

    @property
    def renews(self) -> bool:
        return (
            self.missing is None
            and self.id is not None
            and self.status in _RENEWING_STATUSES
            and not self.cancelling
            and self.cancels_on is None
        )

    @property
    def ends(self) -> bool:
        """Bought, and settled not to renew: set to cancel, cancelled, or paid once."""
        if self.missing is not None:
            return False
        if self.id is None:
            return True
        return self.status == "canceled" or (
            self.status in _RENEWING_STATUSES and self.cancelling
        )

    @property
    def resumable(self) -> bool:
        """Set to cancel: Stripe's portal lets its buyer renew it until its period ends."""
        return self.ends and self.status in _RENEWING_STATUSES

    def describe(self) -> str:
        """One line for the operator: what Stripe holds, and whether it renews."""
        if self.missing is not None:
            return self.missing
        if self.id is None:
            return "paid once, with no subscription, so it does not renew"
        if self.cancels_on is not None:
            return (
                f"subscription {self.id} is set to cancel on {self.cancels_on.date()}, "
                "after it renews once more, prorated: a support case"
            )
        if self.renews:
            on = f" on {self.period_end.date()}" if self.period_end else ""
            return f"subscription {self.id}, renews{on}"
        if self.ends:
            state = "canceled" if self.status == "canceled" else "set to cancel"
            return f"subscription {self.id} is {state}, so it does not renew"
        return (
            f"subscription {self.id} is {self.status or 'in no status'}, neither "
            "renewing nor ended; run again once Stripe settles it"
        )


async def live_subscription(
    metadata: Mapping[str, Any], stripe_client: Any
) -> LiveSubscription:
    """What Stripe says of the license's purchase; Stripe's errors propagate.

    An object Stripe does not have is an answer, not an error: a test-mode id,
    say, which the live account never held.
    """
    subscription_id = str(metadata.get(META_SUBSCRIPTION) or "") or None
    if subscription_id is None:
        session_id = str(metadata.get(META_SESSION) or "") or None
        if session_id is None:
            return LiveSubscription(
                missing="no Stripe purchase on it (issued by hand or invoiced)"
            )
        session = await _retrieve(
            stripe_client.v1.checkout.sessions.retrieve, session_id
        )
        if session is None:
            return LiveSubscription(
                missing=f"its checkout session {session_id} is not in this Stripe account"
            )
        subscription_id = subscription_of_checkout(session)
        if subscription_id is None:
            return await _paid_once(session, session_id, stripe_client)
    subscription = await _retrieve(
        partial(stripe_client.v1.subscriptions.retrieve, params={"expand": _EXPAND}),
        subscription_id,
    )
    if subscription is None:
        return LiveSubscription(
            subscription_id,
            missing=f"its subscription {subscription_id} is not in this Stripe account",
        )

    status = str(getattr(subscription, "status", "") or "") or None
    end = period_end(subscription)
    if status == "canceled":
        # Retries that fail end it after Stripe moved the period to a year not paid for.
        end = _earlier(end, _moment(getattr(subscription, "ended_at", None)))
    at_period_end = bool(getattr(subscription, "cancel_at_period_end", False))
    cancel_at = _moment(getattr(subscription, "cancel_at", None))
    # Stripe docs: a cancel date within the period moves its end there; a later one
    # leaves the cycle alone until the subscription renews into that date.
    later = (
        cancel_at is not None
        and not at_period_end
        and status in _RENEWING_STATUSES
        and (end is None or cancel_at > end)
    )
    invoices = await _period_invoices(subscription_id, stripe_client)
    return LiveSubscription(
        subscription_id,
        status=status,
        cancelling=at_period_end or (cancel_at is not None and not later),
        cancels_on=cancel_at if later else None,
        period_end=end,
        paid_through=end + GRACE if end else None,
        people=people(subscription),
        returned=await period_payment_returned(invoices, stripe_client),
        renews_above_price_paid=renews_above_price_paid(
            subscription, invoices[0] if invoices else None
        ),
    )


async def _paid_once(
    session: Any, session_id: str, stripe_client: Any
) -> LiveSubscription:
    """A checkout with no subscription is a purchase only when it was paid in payment mode."""
    mode = getattr(session, "mode", None)
    status = getattr(session, "status", None)
    paid = getattr(session, "payment_status", None)
    if mode != "payment" or status != "complete" or paid not in PAID_STATUSES:
        return LiveSubscription(
            missing=(
                f"its checkout session {session_id} ({mode} mode) is {status}, "
                f"{paid}: not a purchase"
            )
        )
    return LiveSubscription(
        returned=await payment_intent_returned(
            getattr(session, "payment_intent", None), stripe_client
        )
    )


async def _period_invoices(subscription_id: str, stripe_client: Any) -> list[Any]:
    """The paid invoices that bought its periods, newest first."""
    page = await anyio.to_thread.run_sync(
        partial(
            stripe_client.v1.invoices.list,
            params={"subscription": subscription_id, "status": "paid", "limit": 100},
        )
    )
    return [
        invoice
        for invoice in getattr(page, "data", None) or []
        if getattr(invoice, "billing_reason", None) in PERIOD_BILLING_REASONS
    ]


async def _retrieve(retrieve_one: Callable[[str], Any], object_id: str) -> Any | None:
    """The object, or ``None`` when this Stripe account has no such object."""
    try:
        # In a thread, as every Stripe call in the backend.
        return await anyio.to_thread.run_sync(retrieve_one, object_id)
    except stripe.InvalidRequestError as error:
        if error.http_status == 404:
            return None
        raise


def _moment(timestamp: Any) -> datetime | None:
    return (
        datetime.fromtimestamp(timestamp, UTC) if isinstance(timestamp, int) else None
    )


def _earlier(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None or second is None:
        return first or second
    return min(first, second)
