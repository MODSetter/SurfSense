"""Debit-triggered off-session credit auto-reload.

Enqueued (best-effort) by ``auto_reload_service.maybe_trigger_auto_reload``
after a credit debit drops the wallet below the user's threshold. This task is
the authoritative path: it re-checks eligibility under a row lock, enforces the
cooldown, then charges the saved card off-session via a Stripe PaymentIntent
(Stripe: charging a saved card off-session).

Idempotency comes from three layers:
- a per-attempt CreditPurchase row created PENDING before the charge,
- a Stripe idempotency key derived from that row id,
- the ``payment_intent.*`` webhook backstop in ``stripe_routes`` that only
  transitions PENDING rows.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from stripe import CardError, StripeClient, StripeError

from app.celery_app import celery_app
from app.config import config
from app.db import CreditPurchase, CreditPurchaseStatus, User
from app.notifications.service import NotificationService
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

# 1_000_000 micro-USD == $1.00 == 100 cents, so cents = micros / 10_000.
_MICROS_PER_CENT = 10_000


def _get_stripe_client() -> StripeClient | None:
    if not config.STRIPE_SECRET_KEY:
        logger.warning("Auto-reload skipped because STRIPE_SECRET_KEY is not set.")
        return None
    return StripeClient(config.STRIPE_SECRET_KEY)


def _card_error_payment_intent_id(exc: CardError) -> str | None:
    """Pull the PaymentIntent id off a declined off-session charge.

    Per Stripe's off-session guide the failed intent is on ``exc.error.payment_intent``,
    which may be a StripeObject or a plain dict depending on the SDK path.
    """
    err = getattr(exc, "error", None)
    pi = getattr(err, "payment_intent", None) if err is not None else None
    if pi is None:
        return None
    if isinstance(pi, dict):
        return pi.get("id")
    return getattr(pi, "id", None)


@celery_app.task(name="auto_reload_credits")
def auto_reload_credits_task(user_id: str):
    """Charge the user's saved card to top up credits when below threshold."""
    return run_async_celery_task(_auto_reload_credits, user_id)


async def _auto_reload_credits(user_id: str) -> None:
    if not config.AUTO_RELOAD_ENABLED:
        return

    stripe_client = _get_stripe_client()
    if stripe_client is None:
        return

    cooldown = timedelta(minutes=max(config.AUTO_RELOAD_COOLDOWN_MINUTES, 0))
    now = datetime.now(UTC)
    cutoff = now - cooldown

    async with get_celery_session_maker()() as db_session:
        # Lock the user row so concurrent debits/tasks can't double-charge.
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
        if user is None or not user.auto_reload_enabled:
            return

        if not (user.stripe_customer_id and user.auto_reload_payment_method_id):
            return

        threshold = user.auto_reload_threshold_micros
        amount = user.auto_reload_amount_micros
        if not threshold or not amount:
            return

        available = user.credit_micros_balance - user.credit_micros_reserved
        if available >= threshold:
            # Another reload (or a refund/grant) already restored the balance.
            return

        # Cooldown: skip if a recent auto-reload purchase or failure happened.
        recent = (
            await db_session.execute(
                select(CreditPurchase.id)
                .where(
                    CreditPurchase.user_id == user.id,
                    CreditPurchase.source == "auto_reload",
                    CreditPurchase.created_at >= cutoff,
                    CreditPurchase.status.in_(
                        [
                            CreditPurchaseStatus.PENDING,
                            CreditPurchaseStatus.COMPLETED,
                        ]
                    ),
                )
                .limit(1)
            )
        ).first()
        if recent is not None:
            return
        if user.auto_reload_failed_at and user.auto_reload_failed_at >= cutoff:
            return

        customer_id = user.stripe_customer_id
        payment_method_id = user.auto_reload_payment_method_id
        amount_cents = max(round(amount / _MICROS_PER_CENT), 1)

        # Create the PENDING purchase row first so its id seeds the Stripe
        # idempotency key and the webhook backstop can find it.
        purchase = CreditPurchase(
            user_id=user.id,
            stripe_checkout_session_id=f"auto_reload:{uuid.uuid4()}",
            quantity=0,
            credit_micros_granted=amount,
            amount_total=amount_cents,
            currency="usd",
            source="auto_reload",
            status=CreditPurchaseStatus.PENDING,
        )
        db_session.add(purchase)
        await db_session.flush()
        purchase_id = purchase.id
        await db_session.commit()

    # Charge off-session outside the user-row lock so the network call doesn't
    # hold the row. The purchase row is the synchronization point now.
    try:
        payment_intent = stripe_client.v1.payment_intents.create(
            params={
                "amount": amount_cents,
                "currency": "usd",
                "customer": customer_id,
                "payment_method": payment_method_id,
                "off_session": True,
                "confirm": True,
                "metadata": {
                    "user_id": str(user_id),
                    "purchase_type": "auto_reload",
                    "purchase_id": str(purchase_id),
                },
            },
            options={"idempotency_key": f"auto_reload:{purchase_id}"},
        )
    except CardError as exc:
        await _record_failure(
            purchase_id,
            user_id,
            amount,
            payment_intent_id=_card_error_payment_intent_id(exc),
            reason=getattr(exc, "user_message", None) or "Your card was declined.",
        )
        return
    except StripeError:
        logger.exception("Auto-reload charge failed for user %s", user_id)
        await _record_failure(
            purchase_id,
            user_id,
            amount,
            payment_intent_id=None,
            reason="We couldn't process the charge. Please try again.",
        )
        return

    payment_intent_id = str(payment_intent.id)
    pi_status = getattr(payment_intent, "status", None)

    async with get_celery_session_maker()() as db_session:
        purchase = (
            await db_session.execute(
                select(CreditPurchase)
                .where(CreditPurchase.id == purchase_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if purchase is None:
            return
        purchase.stripe_payment_intent_id = payment_intent_id

        if pi_status == "succeeded":
            if purchase.status != CreditPurchaseStatus.COMPLETED:
                user = (
                    (
                        await db_session.execute(
                            select(User)
                            .where(User.id == purchase.user_id)
                            .with_for_update(of=User)
                        )
                    )
                    .unique()
                    .scalar_one()
                )
                purchase.status = CreditPurchaseStatus.COMPLETED
                purchase.completed_at = datetime.now(UTC)
                user.credit_micros_balance = (
                    user.credit_micros_balance + purchase.credit_micros_granted
                )
                user.auto_reload_failed_at = None
            await db_session.commit()
            logger.info(
                "Auto-reload succeeded for user %s (+%s micro-USD)",
                user_id,
                amount,
            )
            return

        # Not succeeded synchronously (e.g. requires_action / processing).
        # Leave the row PENDING; the payment_intent webhook reconciles it.
        await db_session.commit()
        logger.info(
            "Auto-reload PaymentIntent %s for user %s is %s; awaiting webhook.",
            payment_intent_id,
            user_id,
            pi_status,
        )


async def _record_failure(
    purchase_id: uuid.UUID,
    user_id: str,
    amount_micros: int,
    *,
    payment_intent_id: str | None,
    reason: str | None,
) -> None:
    """Mark the purchase FAILED, stamp the user, and notify them."""
    async with get_celery_session_maker()() as db_session:
        purchase = (
            await db_session.execute(
                select(CreditPurchase)
                .where(CreditPurchase.id == purchase_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if purchase is not None and purchase.status == CreditPurchaseStatus.PENDING:
            purchase.status = CreditPurchaseStatus.FAILED
            if payment_intent_id:
                purchase.stripe_payment_intent_id = payment_intent_id

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
        if user is not None:
            user.auto_reload_failed_at = datetime.now(UTC)
            # Disable so a declined card doesn't get retried every debit; the
            # user re-enables from settings (which clears the failure flag).
            user.auto_reload_enabled = False

        await db_session.commit()

        try:
            await NotificationService.auto_reload_failed.notify_auto_reload_failed(
                session=db_session,
                user_id=uuid.UUID(user_id),
                amount_micros=amount_micros,
                payment_intent_id=payment_intent_id,
                reason=reason,
            )
        except Exception:
            logger.warning(
                "Failed to create auto_reload_failed notification for user %s",
                user_id,
                exc_info=True,
            )
