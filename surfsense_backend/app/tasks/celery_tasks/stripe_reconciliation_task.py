"""Reconcile pending Stripe page purchases that might miss webhook fulfillment."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from stripe import StripeClient, StripeError

from app.celery_app import celery_app
from app.config import config
from app.db import PagePurchase, PagePurchaseStatus
from app.routes import stripe_routes
from app.tasks.celery_tasks import get_celery_session_maker

logger = logging.getLogger(__name__)


def get_stripe_client() -> StripeClient | None:
    """Return a Stripe client for reconciliation, or None when disabled."""
    if not config.STRIPE_SECRET_KEY:
        logger.warning(
            "Stripe reconciliation skipped because STRIPE_SECRET_KEY is not configured."
        )
        return None
    return StripeClient(config.STRIPE_SECRET_KEY)


@celery_app.task(name="reconcile_pending_stripe_page_purchases")
def reconcile_pending_stripe_page_purchases_task():
    """Recover paid purchases that were left pending due to missed webhook handling."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_reconcile_pending_page_purchases())
    finally:
        loop.close()


async def _reconcile_pending_page_purchases() -> None:
    """Reconcile stale pending page purchases against Stripe source of truth.

    Stripe retries webhook delivery automatically, but best practice is to add an
    application-level reconciliation path in case all retries fail or the endpoint
    is unavailable for an extended window.
    """
    stripe_client = get_stripe_client()
    if stripe_client is None:
        return

    lookback_minutes = max(config.STRIPE_RECONCILIATION_LOOKBACK_MINUTES, 0)
    batch_size = max(config.STRIPE_RECONCILIATION_BATCH_SIZE, 1)
    cutoff = datetime.now(UTC) - timedelta(minutes=lookback_minutes)

    async with get_celery_session_maker()() as db_session:
        pending_purchases = (
            (
                await db_session.execute(
                    select(PagePurchase)
                    .where(
                        PagePurchase.status == PagePurchaseStatus.PENDING,
                        PagePurchase.created_at <= cutoff,
                    )
                    .order_by(PagePurchase.created_at.asc())
                    .limit(batch_size)
                )
            )
            .scalars()
            .all()
        )

        if not pending_purchases:
            logger.debug(
                "Stripe reconciliation found no pending purchases older than %s minutes.",
                lookback_minutes,
            )
            return

        logger.info(
            "Stripe reconciliation checking %s pending purchases (cutoff=%s, batch=%s).",
            len(pending_purchases),
            lookback_minutes,
            batch_size,
        )

        fulfilled_count = 0
        failed_count = 0

        for purchase in pending_purchases:
            checkout_session_id = purchase.stripe_checkout_session_id

            try:
                checkout_session = stripe_client.v1.checkout.sessions.retrieve(
                    checkout_session_id
                )
            except StripeError:
                logger.exception(
                    "Stripe reconciliation failed to retrieve checkout session %s",
                    checkout_session_id,
                )
                await db_session.rollback()
                continue

            payment_status = getattr(checkout_session, "payment_status", None)
            session_status = getattr(checkout_session, "status", None)

            try:
                if payment_status in {"paid", "no_payment_required"}:
                    await stripe_routes._fulfill_completed_purchase(
                        db_session, checkout_session
                    )
                    fulfilled_count += 1
                elif session_status == "expired":
                    await stripe_routes._mark_purchase_failed(
                        db_session, str(checkout_session.id)
                    )
                    failed_count += 1
            except Exception:
                logger.exception(
                    "Stripe reconciliation failed while processing checkout session %s",
                    checkout_session_id,
                )
                await db_session.rollback()

        logger.info(
            "Stripe reconciliation completed. fulfilled=%s failed=%s checked=%s",
            fulfilled_count,
            failed_count,
            len(pending_purchases),
        )
