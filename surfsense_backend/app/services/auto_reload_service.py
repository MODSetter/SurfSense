"""Debit-triggered credit auto-reload.

``maybe_trigger_auto_reload`` is a cheap, best-effort pre-filter invoked after
every credit debit (ETL ``charge_credits`` and premium ``credit_finalize``).
When the wallet drops below the user's configured threshold it enqueues the
Celery task that performs the authoritative re-check and the off-session Stripe
charge. All real safety (row lock, cooldown, Stripe idempotency) lives in the
task — this function only avoids enqueuing work that obviously isn't needed.

Everything here is gated behind ``config.AUTO_RELOAD_ENABLED``; when the flag is
off this module is inert.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.config import config

logger = logging.getLogger(__name__)


async def maybe_trigger_auto_reload(user_id: str) -> None:
    """Enqueue an auto-reload charge if the user's balance fell below threshold.

    Best-effort: any failure is swallowed by the caller. Opens its own
    short-lived session so it never interferes with the caller's transaction
    (it always runs after the caller has already committed the debit).
    """
    if not config.AUTO_RELOAD_ENABLED:
        return

    from app.db import CreditPurchase, CreditPurchaseStatus, User, async_session_maker

    async with async_session_maker() as session:
        user = (
            (await session.execute(select(User).where(User.id == user_id)))
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
            return

        # Cheap cooldown pre-check: skip if a recent auto-reload purchase exists
        # or a recent attempt failed (avoids hammering a declined card).
        cutoff = datetime.now(UTC) - timedelta(
            minutes=max(config.AUTO_RELOAD_COOLDOWN_MINUTES, 0)
        )
        if user.auto_reload_failed_at and user.auto_reload_failed_at >= cutoff:
            return
        recent = (
            await session.execute(
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

    # Enqueue outside the session. The task re-checks everything with a row
    # lock before charging, so a benign race here only costs a no-op task run.
    try:
        from app.tasks.celery_tasks.auto_reload_task import (
            auto_reload_credits_task,
        )

        auto_reload_credits_task.delay(str(user_id))
    except Exception:
        logger.warning(
            "Failed to enqueue auto_reload_credits task for user %s",
            user_id,
            exc_info=True,
        )
