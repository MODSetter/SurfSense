"""Topping the wallet up off-session from a saved card.

The card is saved by a ``mode=setup`` checkout; the charge itself is made by
the Celery task, with the ``payment_intent.*`` webhook as a backstop.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient, StripeError

from app.config import config
from app.db import CreditPurchase, CreditPurchaseStatus, User

from . import registry
from .client import get_metadata, normalize_optional_string
from .credits import capture_credits_purchased
from .schemas import AutoReloadSettingsResponse, StripeWebhookResponse

logger = logging.getLogger(__name__)


def ensure_auto_reload_enabled() -> None:
    if not config.AUTO_RELOAD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auto-reload is not available.",
        )


def settings_response(user: User) -> AutoReloadSettingsResponse:
    return AutoReloadSettingsResponse(
        feature_enabled=config.AUTO_RELOAD_ENABLED,
        enabled=bool(user.auto_reload_enabled),
        threshold_micros=user.auto_reload_threshold_micros,
        amount_micros=user.auto_reload_amount_micros,
        min_amount_micros=config.AUTO_RELOAD_MIN_AMOUNT_MICROS,
        has_payment_method=bool(user.auto_reload_payment_method_id),
        failed_at=user.auto_reload_failed_at,
    )


async def handle_setup_session_completed(
    stripe_client: StripeClient,
    db_session: AsyncSession,
    checkout_session: Any,
) -> StripeWebhookResponse:
    """Persist the saved card from a completed ``mode=setup`` checkout session.

    The setup session saves a card on the customer (Stripe save-and-reuse). We
    pull the resulting payment method off the SetupIntent and store it as the
    user's ``auto_reload_payment_method_id`` so the off-session charge can use
    it. Auto-reload itself is only armed once the user enables it via the
    settings endpoint.
    """
    metadata = get_metadata(checkout_session)
    user_id = metadata.get("user_id")
    if not user_id:
        logger.warning(
            "Setup session %s completed without user_id metadata",
            getattr(checkout_session, "id", "?"),
        )
        return StripeWebhookResponse()

    setup_intent_id = normalize_optional_string(
        getattr(checkout_session, "setup_intent", None)
    )
    payment_method_id: str | None = None
    if setup_intent_id:
        try:
            setup_intent = stripe_client.v1.setup_intents.retrieve(setup_intent_id)
            payment_method_id = normalize_optional_string(
                getattr(setup_intent, "payment_method", None)
            )
        except StripeError:
            logger.exception(
                "Failed to retrieve setup intent %s for session %s",
                setup_intent_id,
                getattr(checkout_session, "id", "?"),
            )

    if not payment_method_id:
        logger.warning(
            "Setup session %s completed without a payment method",
            getattr(checkout_session, "id", "?"),
        )
        return StripeWebhookResponse()

    user = (
        (
            await db_session.execute(
                select(User)
                .where(User.id == uuid.UUID(user_id))
                .with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if user is None:
        return StripeWebhookResponse()

    customer_id = normalize_optional_string(getattr(checkout_session, "customer", None))
    if customer_id and not user.stripe_customer_id:
        user.stripe_customer_id = customer_id
    user.auto_reload_payment_method_id = payment_method_id
    await db_session.commit()

    # Make this the customer's default for future off-session charges.
    if user.stripe_customer_id:
        try:
            stripe_client.v1.customers.update(
                user.stripe_customer_id,
                params={
                    "invoice_settings": {"default_payment_method": payment_method_id}
                },
            )
        except StripeError:
            logger.warning(
                "Failed to set default payment method for customer %s",
                user.stripe_customer_id,
                exc_info=True,
            )

    return StripeWebhookResponse()


async def reconcile_payment_intent(
    db_session: AsyncSession,
    payment_intent: Any,
    *,
    succeeded: bool,
) -> StripeWebhookResponse:
    """Backstop for the off-session auto-reload charge via webhook.

    The Celery task confirms the PaymentIntent synchronously and grants credit
    inline, but the ``payment_intent.succeeded`` / ``payment_intent.payment_failed``
    webhook acts as a safety net. We locate the matching ``auto_reload``
    CreditPurchase by payment-intent id and only transition PENDING rows so we
    never double-grant.
    """
    payment_intent_id = str(payment_intent.id)
    purchase = (
        await db_session.execute(
            select(CreditPurchase)
            .where(CreditPurchase.stripe_payment_intent_id == payment_intent_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is None or purchase.status != CreditPurchaseStatus.PENDING:
        return StripeWebhookResponse()

    if succeeded:
        user = (
            (
                await db_session.execute(
                    select(User)
                    .where(User.id == purchase.user_id)
                    .with_for_update(of=User)
                )
            )
            .unique()
            .scalar_one_or_none()
        )
        if user is None:
            return StripeWebhookResponse()
        purchase.status = CreditPurchaseStatus.COMPLETED
        purchase.completed_at = datetime.now(UTC)
        user.credit_micros_balance = (
            user.credit_micros_balance + purchase.credit_micros_granted
        )
    else:
        purchase.status = CreditPurchaseStatus.FAILED

    await db_session.commit()
    if succeeded:
        capture_credits_purchased(user, purchase)
    return StripeWebhookResponse()


async def _handle_setup(
    checkout_session: Any,
    *,
    db_session: AsyncSession,
    stripe_client: StripeClient,
    **_: Any,
) -> StripeWebhookResponse:
    return await handle_setup_session_completed(
        stripe_client, db_session, checkout_session
    )


async def _reconcile_succeeded(
    payment_intent: Any, *, db_session: AsyncSession, **_: Any
) -> StripeWebhookResponse:
    return await reconcile_payment_intent(db_session, payment_intent, succeeded=True)


async def _reconcile_failed(
    payment_intent: Any, *, db_session: AsyncSession, **_: Any
) -> StripeWebhookResponse:
    return await reconcile_payment_intent(db_session, payment_intent, succeeded=False)


registry.claims_checkout(
    "auto_reload_setup",
    # A setup session saves a card and buys nothing, so it carries no line
    # items for anyone else's claim to match on.
    lambda _metadata, session, _client: getattr(session, "mode", None) == "setup",
    _handle_setup,
)
registry.on_event("payment_intent.succeeded", _reconcile_succeeded)
registry.on_event("payment_intent.payment_failed", _reconcile_failed)
