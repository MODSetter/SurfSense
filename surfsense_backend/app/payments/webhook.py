"""The Stripe webhook endpoint: verify the signature, hand the event on."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import SignatureVerificationError

from app.config import config
from app.db import get_async_session

from . import registry
from .client import get_metadata, get_stripe_client
from .schemas import StripeWebhookResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Both mean "the money is in"; Stripe sends the async one when the payment
# method settles after the session closes.
_PAID_CHECKOUT_EVENTS = frozenset(
    {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
)
_SETTLED_PAYMENT_STATUSES = frozenset({"paid", "no_payment_required"})


@router.post("/webhook", response_model=StripeWebhookResponse)
async def stripe_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
) -> StripeWebhookResponse:
    """Verify a Stripe webhook and route it to whoever registered for it."""
    if not config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook handling is not configured.",
        )

    stripe_client = get_stripe_client()
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")

    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )

    try:
        event = stripe_client.construct_event(
            payload,
            signature,
            config.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook payload.",
        ) from exc
    except SignatureVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        ) from exc

    try:
        if event.type in _PAID_CHECKOUT_EVENTS:
            checkout_session = event.data.object
            payment_status = getattr(checkout_session, "payment_status", None)

            if (
                event.type == "checkout.session.completed"
                and payment_status not in _SETTLED_PAYMENT_STATUSES
            ):
                logger.info(
                    "Received checkout.session.completed for unpaid session %s; waiting for async success.",
                    checkout_session.id,
                )
                return StripeWebhookResponse()

            metadata = get_metadata(checkout_session)
            handler = registry.checkout_handler(
                metadata, checkout_session, stripe_client
            )
            if handler is None:
                logger.info(
                    "No handler claimed checkout session %s (purchase_type=%s)",
                    getattr(checkout_session, "id", "?"),
                    metadata.get("purchase_type"),
                )
                return StripeWebhookResponse()
            return await handler(
                checkout_session,
                db_session=db_session,
                stripe_client=stripe_client,
            )

        handler = registry.event_handler(event.type)
        if handler is not None:
            return await handler(
                event.data.object,
                db_session=db_session,
                stripe_client=stripe_client,
            )
    except Exception:
        logger.exception(
            "Stripe webhook handler failed for event id=%s type=%s — Stripe will retry",
            getattr(event, "id", "?"),
            getattr(event, "type", "?"),
        )
        raise

    return StripeWebhookResponse()
