"""`POST /stripe/webhook`: verify Stripe's signature, then fulfil a license purchase or suspend a refunded one.

surfsense_backend's credit purchases stayed with it; any other event is acknowledged and dropped.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from stripe import SignatureVerificationError

from license.purchase import claims_checkout, fulfill, suspend_refunded
from license.settings import config
from license.stripe_client import get_metadata, get_stripe_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])

# Both mean the money is in; Stripe sends the async one when the payment settles after the session closes.
_PAID_CHECKOUT_EVENTS = frozenset(
    {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
)
_SETTLED_PAYMENT_STATUSES = frozenset({"paid", "no_payment_required"})


class StripeWebhookResponse(BaseModel):
    received: bool = True


@router.post("/webhook")
async def stripe_webhook(request: Request) -> StripeWebhookResponse:
    stripe_client = get_stripe_client()
    if not config.STRIPE_WEBHOOK_SECRET or stripe_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook handling is not configured.",
        )

    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header.",
        )
    try:
        event = stripe_client.construct_event(
            payload, signature, config.STRIPE_WEBHOOK_SECRET
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
            if await claims_checkout(metadata, checkout_session, stripe_client):
                await fulfill(checkout_session, stripe_client=stripe_client)
            else:
                logger.info(
                    "Checkout session %s is not a license purchase (purchase_type=%s)",
                    getattr(checkout_session, "id", "?"),
                    metadata.get("purchase_type"),
                )
        elif event.type == "charge.refunded":
            await suspend_refunded(event.data.object, stripe_client=stripe_client)
    except Exception:
        # A 500 makes Stripe retry, which the fulfilment's derived license id makes safe.
        logger.exception(
            "Stripe webhook handler failed for event id=%s type=%s; Stripe will retry",
            getattr(event, "id", "?"),
            getattr(event, "type", "?"),
        )
        raise
    return StripeWebhookResponse()
