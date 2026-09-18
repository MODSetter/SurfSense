"""Buying and granting wallet credit.

A pack grants ``STRIPE_CREDIT_MICROS_PER_UNIT`` micro-USD (default
1_000_000 == $1.00) into ``user.credit_micros_balance``, which ETL page
processing and premium model calls both debit.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import CreditPurchase, CreditPurchaseStatus, User
from app.observability.analytics import posthog as ph_analytics

from . import registry
from .client import get_metadata, normalize_optional_string
from .schemas import StripeWebhookResponse

logger = logging.getLogger(__name__)

# Canonical purchase_type metadata value is ``credits``. ``premium_tokens`` and
# ``premium_credit`` were emitted by earlier releases so they're still accepted
# on the read side for any in-flight checkout sessions.
PURCHASE_TYPE_CREDIT_VALUES = frozenset({"credits", "premium_tokens", "premium_credit"})


def capture_credits_purchased(user: User, purchase: CreditPurchase) -> None:
    """Emit ``credits_purchased`` — revenue events only exist server-side.

    Call only from the idempotent grant paths (which early-return on already
    COMPLETED / non-PENDING rows) so Stripe retries never double-count. No-op
    when PostHog is unconfigured.
    """
    ph_analytics.capture(
        "credits_purchased",
        distinct_id=str(user.id),
        properties={
            "credit_micros_granted": purchase.credit_micros_granted,
            "quantity": purchase.quantity,
            "amount_total": purchase.amount_total,
            "currency": purchase.currency,
            "source": purchase.source,
        },
    )


def ensure_credit_buying_enabled() -> None:
    if not config.STRIPE_CREDIT_BUYING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credit purchases are temporarily unavailable.",
        )


def get_checkout_urls(workspace_id: int) -> tuple[str, str]:
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )

    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    # Stripe substitutes ``{CHECKOUT_SESSION_ID}`` with the actual session id
    # at redirect time. The frontend uses it to call /stripe/finalize-checkout
    # which fulfils synchronously without waiting for the webhook — fixing the
    # webhook-vs-redirect race where users land on /purchase-success before
    # checkout.session.completed has been delivered.
    success_url = (
        f"{base_url}/dashboard/{workspace_id}/purchase-success"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = f"{base_url}/dashboard/{workspace_id}/purchase-cancel"
    return success_url, cancel_url


def get_required_credit_price_id() -> str:
    if not config.STRIPE_CREDIT_PRICE_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_CREDIT_PRICE_ID is not configured.",
        )
    return config.STRIPE_CREDIT_PRICE_ID


def is_credit_purchase(metadata: dict[str, str]) -> bool:
    """Return True for a credit purchase (default for all live checkouts)."""
    return metadata.get("purchase_type", "credits") in PURCHASE_TYPE_CREDIT_VALUES


async def mark_credit_purchase_failed(
    db_session: AsyncSession, checkout_session_id: str
) -> StripeWebhookResponse:
    purchase = (
        await db_session.execute(
            select(CreditPurchase)
            .where(CreditPurchase.stripe_checkout_session_id == checkout_session_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is not None and purchase.status == CreditPurchaseStatus.PENDING:
        purchase.status = CreditPurchaseStatus.FAILED
        await db_session.commit()

    return StripeWebhookResponse()


async def fulfill_completed_credit_purchase(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Grant credit to the user after a confirmed Stripe payment.

    Uses ``SELECT ... FOR UPDATE`` on both the CreditPurchase and User rows to
    prevent double-granting when Stripe retries the webhook concurrently.
    """
    checkout_session_id = str(checkout_session.id)
    purchase = (
        await db_session.execute(
            select(CreditPurchase)
            .where(CreditPurchase.stripe_checkout_session_id == checkout_session_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is None:
        metadata = get_metadata(checkout_session)
        user_id = metadata.get("user_id")
        quantity = int(metadata.get("quantity", "0"))
        # Read the new metadata key first, fall back to legacy ones so
        # in-flight checkout sessions created before the rename still fulfil.
        credit_micros_per_unit = int(
            metadata.get("credit_micros_per_unit")
            or metadata.get("tokens_per_unit", "0")
        )

        if not user_id or quantity <= 0 or credit_micros_per_unit <= 0:
            logger.error(
                "Skipping credit fulfillment for session %s: incomplete metadata %s",
                checkout_session_id,
                metadata,
            )
            return StripeWebhookResponse()

        purchase = CreditPurchase(
            user_id=uuid.UUID(user_id),
            stripe_checkout_session_id=checkout_session_id,
            stripe_payment_intent_id=normalize_optional_string(
                getattr(checkout_session, "payment_intent", None)
            ),
            quantity=quantity,
            credit_micros_granted=quantity * credit_micros_per_unit,
            amount_total=getattr(checkout_session, "amount_total", None),
            currency=getattr(checkout_session, "currency", None),
            source="checkout",
            status=CreditPurchaseStatus.PENDING,
        )
        db_session.add(purchase)
        await db_session.flush()

    if purchase.status == CreditPurchaseStatus.COMPLETED:
        return StripeWebhookResponse()

    user = (
        (
            await db_session.execute(
                select(User).where(User.id == purchase.user_id).with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if user is None:
        logger.error(
            "Skipping credit fulfillment for session %s: user %s not found",
            purchase.stripe_checkout_session_id,
            purchase.user_id,
        )
        return StripeWebhookResponse()

    purchase.status = CreditPurchaseStatus.COMPLETED
    purchase.completed_at = datetime.now(UTC)
    purchase.amount_total = getattr(checkout_session, "amount_total", None)
    purchase.currency = getattr(checkout_session, "currency", None)
    purchase.stripe_payment_intent_id = normalize_optional_string(
        getattr(checkout_session, "payment_intent", None)
    )
    # Add the granted micro-USD directly to the spendable wallet balance.
    user.credit_micros_balance = (
        user.credit_micros_balance + purchase.credit_micros_granted
    )

    await db_session.commit()
    capture_credits_purchased(user, purchase)
    return StripeWebhookResponse()


async def _fulfill_claimed(
    checkout_session: Any, *, db_session: AsyncSession, **_: Any
) -> StripeWebhookResponse:
    return await fulfill_completed_credit_purchase(db_session, checkout_session)


async def _fulfill_unclaimed(
    checkout_session: Any, *, db_session: AsyncSession, **_: Any
) -> StripeWebhookResponse:
    """Settle a paid session nobody recognised.

    A live credit checkout carries no ``purchase_type`` of its own, so absence
    means credit. An explicit but unknown one is a legacy page pack; page
    buying is removed, so log it rather than granting anything.
    """
    metadata = get_metadata(checkout_session)
    if is_credit_purchase(metadata):
        return await fulfill_completed_credit_purchase(db_session, checkout_session)

    logger.info(
        "Ignoring non-credit checkout session %s (purchase_type=%s); "
        "page buying is removed.",
        getattr(checkout_session, "id", "?"),
        metadata.get("purchase_type"),
    )
    return StripeWebhookResponse()


async def _mark_failed_if_credit(
    checkout_session: Any, *, db_session: AsyncSession, **_: Any
) -> StripeWebhookResponse:
    if is_credit_purchase(get_metadata(checkout_session)):
        return await mark_credit_purchase_failed(db_session, str(checkout_session.id))
    return StripeWebhookResponse()


def _claims_checkout(
    metadata: dict[str, str], _checkout_session: Any, _stripe_client: Any
) -> bool:
    # Strict on purpose: the "no purchase_type means credit" default lives in
    # the fallback, so this claim cannot collide with anyone else's.
    return metadata.get("purchase_type") in PURCHASE_TYPE_CREDIT_VALUES


registry.claims_checkout("credits", _claims_checkout, _fulfill_claimed)
registry.falls_back_to(_fulfill_unclaimed, name="credits")
registry.on_event("checkout.session.async_payment_failed", _mark_failed_if_credit)
registry.on_event("checkout.session.expired", _mark_failed_if_credit)
