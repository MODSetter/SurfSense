"""Stripe routes for pay-as-you-go page purchases and subscriptions."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import SignatureVerificationError, StripeClient, StripeError

from app.config import config
from app.db import (
    PagePurchase,
    PagePurchaseStatus,
    SubscriptionRequest,
    SubscriptionRequestStatus,
    SubscriptionStatus,
    User,
    get_async_session,
)
from app.schemas.stripe import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    CreateSubscriptionCheckoutRequest,
    CreateSubscriptionCheckoutResponse,
    PagePurchaseHistoryResponse,
    PlanId,
    StripeStatusResponse,
    StripeWebhookResponse,
)
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for verify-checkout-session (20 calls/60 s)
# Not persistent across workers — acceptable for the low-risk, low-volume
# nature of this endpoint.
# ---------------------------------------------------------------------------
_VERIFY_SESSION_WINDOW_SECS = 60
_VERIFY_SESSION_MAX_CALLS = 20
_verify_session_calls: dict[str, list[float]] = defaultdict(list)


def _check_verify_session_rate_limit(user_id: str) -> None:
    now = datetime.now(UTC).timestamp()
    cutoff = now - _VERIFY_SESSION_WINDOW_SECS
    calls = [t for t in _verify_session_calls[user_id] if t > cutoff]
    if len(calls) >= _VERIFY_SESSION_MAX_CALLS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again later.",
        )
    calls.append(now)
    _verify_session_calls[user_id] = calls


def get_stripe_client() -> StripeClient:
    """Return a configured Stripe client or raise if Stripe is disabled."""
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe checkout is not configured.",
        )
    return StripeClient(config.STRIPE_SECRET_KEY)


def _ensure_page_buying_enabled() -> None:
    if not config.STRIPE_PAGE_BUYING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Page purchases are temporarily unavailable.",
        )


def _get_checkout_urls(search_space_id: int) -> tuple[str, str]:
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )

    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/dashboard/{search_space_id}/purchase-success"
    cancel_url = f"{base_url}/dashboard/{search_space_id}/purchase-cancel"
    return success_url, cancel_url


def _get_required_stripe_price_id() -> str:
    if not config.STRIPE_PRICE_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_PRICE_ID is not configured.",
        )
    return config.STRIPE_PRICE_ID


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "id", str(value))


def _get_subscription_urls() -> tuple[str, str]:
    """Return (success_url, cancel_url) for subscription checkout."""
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    base = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base}/subscription-success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base}/pricing"
    return success_url, cancel_url


def _get_price_id_for_plan(plan_id: PlanId) -> str:
    """Map a plan_id enum to the corresponding Stripe Price ID from env vars."""
    if plan_id == PlanId.pro_monthly:
        price_id = config.STRIPE_PRO_MONTHLY_PRICE_ID
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="STRIPE_PRO_MONTHLY_PRICE_ID is not configured.",
            )
        return price_id
    if plan_id == PlanId.pro_yearly:
        price_id = config.STRIPE_PRO_YEARLY_PRICE_ID
        if not price_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="STRIPE_PRO_YEARLY_PRICE_ID is not configured.",
            )
        return price_id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown plan_id: {plan_id}",
    )


async def _get_or_create_stripe_customer(
    stripe_client: StripeClient,
    user: User,
    db_session: AsyncSession,
) -> str:
    """Return existing Stripe customer ID or create a new one and persist it.

    Uses SELECT ... FOR UPDATE to prevent duplicate customer creation under
    concurrent requests for the same user.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    locked_user = (
        (
            await db_session.execute(
                select(User).where(User.id == user.id).with_for_update()
            )
        )
        .unique()
        .scalar_one()
    )

    # Re-check after acquiring the lock — another request may have created it.
    if locked_user.stripe_customer_id:
        return locked_user.stripe_customer_id

    try:
        customer = stripe_client.v1.customers.create(
            params={
                "email": locked_user.email,
                "metadata": {"user_id": str(locked_user.id)},
            }
        )
    except StripeError as exc:
        logger.exception("Failed to create Stripe customer for user %s", locked_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe customer.",
        ) from exc

    locked_user.stripe_customer_id = str(customer.id)
    await db_session.commit()
    return locked_user.stripe_customer_id


def _get_metadata(checkout_session: Any) -> dict[str, str]:
    metadata = getattr(checkout_session, "metadata", None) or {}
    if isinstance(metadata, dict):
        return {str(key): str(value) for key, value in metadata.items()}
    return dict(metadata)


async def _get_or_create_purchase_from_checkout_session(
    db_session: AsyncSession,
    checkout_session: Any,
) -> PagePurchase | None:
    """Look up a PagePurchase by checkout session ID (with FOR UPDATE lock).

    If the row doesn't exist yet (e.g. the webhook arrived before the API
    response committed), create one from the Stripe session metadata.
    """
    checkout_session_id = str(checkout_session.id)
    purchase = (
        await db_session.execute(
            select(PagePurchase)
            .where(PagePurchase.stripe_checkout_session_id == checkout_session_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if purchase is not None:
        return purchase

    metadata = _get_metadata(checkout_session)
    user_id = metadata.get("user_id")
    quantity = int(metadata.get("quantity", "0"))
    pages_per_unit = int(metadata.get("pages_per_unit", "0"))

    if not user_id or quantity <= 0 or pages_per_unit <= 0:
        logger.error(
            "Skipping Stripe fulfillment for session %s due to incomplete metadata: %s",
            checkout_session_id,
            metadata,
        )
        return None

    purchase = PagePurchase(
        user_id=uuid.UUID(user_id),
        stripe_checkout_session_id=checkout_session_id,
        stripe_payment_intent_id=_normalize_optional_string(
            getattr(checkout_session, "payment_intent", None)
        ),
        quantity=quantity,
        pages_granted=quantity * pages_per_unit,
        amount_total=getattr(checkout_session, "amount_total", None),
        currency=getattr(checkout_session, "currency", None),
        status=PagePurchaseStatus.PENDING,
    )
    db_session.add(purchase)
    await db_session.flush()
    return purchase


async def _mark_purchase_failed(
    db_session: AsyncSession, checkout_session_id: str
) -> StripeWebhookResponse:
    purchase = (
        await db_session.execute(
            select(PagePurchase)
            .where(PagePurchase.stripe_checkout_session_id == checkout_session_id)
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is not None and purchase.status == PagePurchaseStatus.PENDING:
        purchase.status = PagePurchaseStatus.FAILED
        await db_session.commit()

    return StripeWebhookResponse()


async def _fulfill_completed_purchase(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Grant pages to the user after a confirmed Stripe payment.

    Uses SELECT ... FOR UPDATE on both the PagePurchase and User rows to
    prevent double-granting when Stripe retries the webhook concurrently.
    """
    purchase = await _get_or_create_purchase_from_checkout_session(
        db_session, checkout_session
    )
    if purchase is None:
        return StripeWebhookResponse()

    if purchase.status == PagePurchaseStatus.COMPLETED:
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
            "Skipping Stripe fulfillment for session %s because user %s was not found.",
            purchase.stripe_checkout_session_id,
            purchase.user_id,
        )
        return StripeWebhookResponse()

    purchase.status = PagePurchaseStatus.COMPLETED
    purchase.completed_at = datetime.now(UTC)
    purchase.amount_total = getattr(checkout_session, "amount_total", None)
    purchase.currency = getattr(checkout_session, "currency", None)
    purchase.stripe_payment_intent_id = _normalize_optional_string(
        getattr(checkout_session, "payment_intent", None)
    )
    # pages_used can exceed pages_limit when a document's final page count is
    # determined after processing. Base the new limit on the higher of the two
    # so the purchased pages are fully usable above the current high-water mark.
    user.pages_limit = max(user.pages_used, user.pages_limit) + purchase.pages_granted

    await db_session.commit()
    return StripeWebhookResponse()


# ---------------------------------------------------------------------------
# Subscription event helpers
# ---------------------------------------------------------------------------


async def _get_user_by_stripe_customer_id(
    db_session: AsyncSession, customer_id: str
) -> User | None:
    """Fetch the User row for a given Stripe customer ID (with FOR UPDATE lock)."""
    return (
        (
            await db_session.execute(
                select(User)
                .where(User.stripe_customer_id == customer_id)
                .with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )


def _period_end_from_subscription(subscription: Any) -> datetime | None:
    """Extract current_period_end timestamp from a Stripe subscription object."""
    ts = getattr(subscription, "current_period_end", None)
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC)


async def _handle_subscription_event(
    db_session: AsyncSession, subscription: Any
) -> StripeWebhookResponse:
    """Handle customer.subscription.created / updated / deleted.

    Idempotency: compares stripe_subscription_id + current_period_end so
    duplicate events for the same billing period are no-ops.
    """
    customer_id = _normalize_optional_string(getattr(subscription, "customer", None))
    subscription_id = _normalize_optional_string(getattr(subscription, "id", None))
    sub_status = str(getattr(subscription, "status", "")).lower()
    period_end = _period_end_from_subscription(subscription)

    # Determine plan from the first subscription item's price ID
    plan_id: str = "free"
    try:
        items = getattr(subscription, "items", None)
        if items:
            item_data = getattr(items, "data", None) or []
            if item_data:
                price_id = str(getattr(item_data[0].price, "id", ""))
                if price_id == config.STRIPE_PRO_YEARLY_PRICE_ID:
                    plan_id = "pro_yearly"
                elif price_id == config.STRIPE_PRO_MONTHLY_PRICE_ID:
                    plan_id = "pro_monthly"
                else:
                    logger.warning(
                        "Subscription %s has unrecognized price ID %s; defaulting to free limits",
                        subscription_id,
                        price_id,
                    )
    except Exception:
        logger.warning("Could not parse plan from subscription %s", subscription_id)

    if not customer_id:
        logger.error(
            "Subscription event missing customer ID for subscription %s",
            subscription_id,
        )
        return StripeWebhookResponse()

    # Safety: never silently downgrade an active subscription to "free" due to
    # an unrecognized price ID. Return early without modifying the user.
    if (
        plan_id == "free"
        and str(getattr(subscription, "status", "")).lower() == "active"
    ):
        logger.error(
            "Subscription %s is active but price ID is unrecognized — skipping update to avoid downgrade",
            subscription_id,
        )
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping subscription event",
            customer_id,
        )
        return StripeWebhookResponse()

    # Map Stripe status → SubscriptionStatus enum
    if sub_status == "active":
        new_status = SubscriptionStatus.ACTIVE
    elif sub_status in {"canceled", "incomplete_expired"}:
        new_status = SubscriptionStatus.CANCELED
        plan_id = "free"
    elif sub_status == "past_due":
        new_status = SubscriptionStatus.PAST_DUE
    else:
        # incomplete, trialing, unpaid → leave current status unchanged
        logger.info(
            "Ignoring subscription %s with unhandled Stripe status '%s'",
            subscription_id,
            sub_status,
        )
        return StripeWebhookResponse()

    # Idempotency: skip if nothing meaningful changed
    if (
        user.stripe_subscription_id == subscription_id
        and user.subscription_status == new_status
        and user.plan_id == plan_id
        and user.subscription_current_period_end == period_end
    ):
        logger.info("Subscription %s already up-to-date; skipping", subscription_id)
        return StripeWebhookResponse()

    # Update subscription fields
    user.stripe_subscription_id = subscription_id
    user.subscription_status = new_status
    user.plan_id = plan_id
    # Guard against out-of-order webhook delivery: only advance period_end forward
    if period_end is not None and (
        user.subscription_current_period_end is None
        or period_end > user.subscription_current_period_end
    ):
        user.subscription_current_period_end = period_end

    # Update limits from plan config
    limits = config.PLAN_LIMITS.get(plan_id, config.PLAN_LIMITS["free"])
    user.monthly_token_limit = limits["monthly_token_limit"]

    # Upgrade pages_limit on activation; reset token counter date
    if new_status == SubscriptionStatus.ACTIVE:
        user.pages_limit = max(user.pages_used, limits["pages_limit"])
        if user.token_reset_date is None:
            user.token_reset_date = datetime.now(UTC).date()

    # Downgrade pages_limit when canceling
    if new_status == SubscriptionStatus.CANCELED:
        free_limits = config.PLAN_LIMITS["free"]
        user.pages_limit = max(user.pages_used, free_limits["pages_limit"])

    logger.info(
        "Updated subscription for user %s: status=%s plan=%s subscription=%s",
        user.id,
        new_status,
        plan_id,
        subscription_id,
    )
    await db_session.commit()
    return StripeWebhookResponse()


async def _handle_invoice_payment_succeeded(
    db_session: AsyncSession, invoice: Any
) -> StripeWebhookResponse:
    """Reset tokens_used_this_month and advance token_reset_date on billing renewal."""
    customer_id = _normalize_optional_string(getattr(invoice, "customer", None))
    billing_reason = str(getattr(invoice, "billing_reason", "")).lower()

    if not customer_id:
        return StripeWebhookResponse()

    # Reset tokens on subscription renewals and initial subscription creation
    if billing_reason not in {"subscription_cycle", "subscription_create"}:
        logger.info(
            "invoice.payment_succeeded billing_reason=%s; not resetting tokens",
            billing_reason,
        )
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping token reset", customer_id
        )
        return StripeWebhookResponse()

    user.tokens_used_this_month = 0
    user.token_reset_date = datetime.now(UTC).date()

    logger.info(
        "Reset tokens_used_this_month for user %s on subscription renewal", user.id
    )
    await db_session.commit()
    return StripeWebhookResponse()


async def _handle_invoice_payment_failed(
    db_session: AsyncSession, invoice: Any
) -> StripeWebhookResponse:
    """Mark subscription as past_due when a renewal invoice payment fails."""
    customer_id = _normalize_optional_string(getattr(invoice, "customer", None))
    if not customer_id:
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping past_due update",
            customer_id,
        )
        return StripeWebhookResponse()

    if user.subscription_status == SubscriptionStatus.ACTIVE:
        user.subscription_status = SubscriptionStatus.PAST_DUE
        logger.info("Set subscription to PAST_DUE for user %s", user.id)
        await db_session.commit()
    else:
        logger.info(
            "invoice.payment_failed for user %s already in status %s; no change",
            user.id,
            user.subscription_status,
        )

    return StripeWebhookResponse()


async def _activate_subscription_from_checkout(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Activate subscription when checkout.session.completed fires for mode='subscription'.

    The full subscription lifecycle will also be handled by customer.subscription.created,
    but we activate immediately here so the user sees Pro access right after checkout.
    """
    customer_id = _normalize_optional_string(
        getattr(checkout_session, "customer", None)
    )
    subscription_id = _normalize_optional_string(
        getattr(checkout_session, "subscription", None)
    )
    metadata = _get_metadata(checkout_session)
    plan_id_str = metadata.get("plan_id", "")

    if not customer_id:
        logger.error(
            "Subscription checkout session missing customer ID: %s",
            getattr(checkout_session, "id", ""),
        )
        return StripeWebhookResponse()

    user = await _get_user_by_stripe_customer_id(db_session, customer_id)
    if user is None:
        logger.warning(
            "No user found for Stripe customer %s; skipping subscription activation",
            customer_id,
        )
        return StripeWebhookResponse()

    # Idempotency: already activated
    if (
        user.subscription_status == SubscriptionStatus.ACTIVE
        and user.stripe_subscription_id == subscription_id
    ):
        logger.info(
            "Subscription already active for user %s; skipping activation", user.id
        )
        return StripeWebhookResponse()

    plan_id = (
        plan_id_str if plan_id_str in {"pro_monthly", "pro_yearly"} else "pro_monthly"
    )
    limits = config.PLAN_LIMITS.get(plan_id, config.PLAN_LIMITS["pro_monthly"])

    user.subscription_status = SubscriptionStatus.ACTIVE
    user.plan_id = plan_id
    user.stripe_subscription_id = subscription_id
    user.monthly_token_limit = limits["monthly_token_limit"]
    user.pages_limit = max(user.pages_used, limits["pages_limit"])
    user.tokens_used_this_month = 0
    user.token_reset_date = datetime.now(UTC).date()

    # Retrieve subscription object to set period_end (best-effort)
    if subscription_id:
        try:
            stripe_client = get_stripe_client()
            sub_obj = stripe_client.v1.subscriptions.retrieve(subscription_id)
            user.subscription_current_period_end = _period_end_from_subscription(
                sub_obj
            )
        except Exception:
            logger.warning(
                "Could not retrieve subscription %s for period_end", subscription_id
            )

    logger.info(
        "Activated subscription for user %s: plan=%s subscription=%s",
        user.id,
        plan_id,
        subscription_id,
    )
    await db_session.commit()
    return StripeWebhookResponse()


@router.post("/create-checkout-session", response_model=CreateCheckoutSessionResponse)
async def create_checkout_session(
    body: CreateCheckoutSessionRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> CreateCheckoutSessionResponse:
    """Create a Stripe Checkout Session for buying page packs."""
    _ensure_page_buying_enabled()
    stripe_client = get_stripe_client()
    price_id = _get_required_stripe_price_id()
    success_url, cancel_url = _get_checkout_urls(body.search_space_id)
    pages_granted = body.quantity * config.STRIPE_PAGES_PER_UNIT

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [
                    {
                        "price": price_id,
                        "quantity": body.quantity,
                    }
                ],
                "client_reference_id": str(user.id),
                "customer_email": user.email,
                "metadata": {
                    "user_id": str(user.id),
                    "quantity": str(body.quantity),
                    "pages_per_unit": str(config.STRIPE_PAGES_PER_UNIT),
                    "purchase_type": "page_packs",
                },
            }
        )
    except StripeError as exc:
        logger.exception(
            "Failed to create Stripe checkout session for user %s", user.id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe checkout session.",
        ) from exc

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe checkout session did not return a URL.",
        )

    db_session.add(
        PagePurchase(
            user_id=user.id,
            stripe_checkout_session_id=str(checkout_session.id),
            stripe_payment_intent_id=_normalize_optional_string(
                getattr(checkout_session, "payment_intent", None)
            ),
            quantity=body.quantity,
            pages_granted=pages_granted,
            amount_total=getattr(checkout_session, "amount_total", None),
            currency=getattr(checkout_session, "currency", None),
            status=PagePurchaseStatus.PENDING,
        )
    )
    await db_session.commit()

    return CreateCheckoutSessionResponse(checkout_url=checkout_url)


@router.post(
    "/create-subscription-checkout",
    response_model=CreateSubscriptionCheckoutResponse,
)
async def create_subscription_checkout(
    body: CreateSubscriptionCheckoutRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> CreateSubscriptionCheckoutResponse:
    """Create a Stripe Checkout Session for a recurring subscription."""
    # Admin-approval mode: when Stripe is not configured, queue a manual request
    if not config.STRIPE_SECRET_KEY:
        if user.subscription_status == SubscriptionStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an active subscription.",
            )
        existing = await db_session.execute(
            select(SubscriptionRequest)
            .where(SubscriptionRequest.user_id == user.id)
            .where(SubscriptionRequest.status == SubscriptionRequestStatus.PENDING)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have a pending subscription request.",
            )
        cooldown_cutoff = datetime.now(UTC) - timedelta(hours=24)
        recently_rejected = await db_session.execute(
            select(SubscriptionRequest)
            .where(SubscriptionRequest.user_id == user.id)
            .where(SubscriptionRequest.status == SubscriptionRequestStatus.REJECTED)
            .where(SubscriptionRequest.created_at >= cooldown_cutoff)
        )
        if recently_rejected.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Your previous request was rejected. Please wait 24 hours before resubmitting.",
            )
        req = SubscriptionRequest(user_id=user.id, plan_id=body.plan_id.value)
        db_session.add(req)
        await db_session.commit()
        logger.info(
            "Admin-approval subscription request created for user %s (plan=%s)",
            user.id,
            body.plan_id.value,
        )
        return CreateSubscriptionCheckoutResponse(
            checkout_url="", admin_approval_mode=True
        )

    stripe_client = get_stripe_client()
    price_id = _get_price_id_for_plan(body.plan_id)
    success_url, cancel_url = _get_subscription_urls()

    # Prevent duplicate subscriptions
    if user.subscription_status == SubscriptionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active subscription.",
        )

    customer_id = await _get_or_create_stripe_customer(stripe_client, user, db_session)

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "customer": customer_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
                "line_items": [{"price": price_id, "quantity": 1}],
                "metadata": {
                    "user_id": str(user.id),
                    "plan_id": body.plan_id.value,
                },
            }
        )
    except StripeError as exc:
        logger.exception(
            "Failed to create Stripe subscription checkout for user %s", user.id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe subscription checkout session.",
        ) from exc

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe subscription checkout session did not return a URL.",
        )

    return CreateSubscriptionCheckoutResponse(checkout_url=checkout_url)


@router.get("/verify-checkout-session")
async def verify_checkout_session(
    session_id: str,
    user: User = Depends(current_active_user),
) -> dict:
    """Verify a Stripe Checkout Session belongs to the user and is paid."""
    _check_verify_session_rate_limit(str(user.id))
    stripe_client = get_stripe_client()
    try:
        session = stripe_client.v1.checkout.sessions.retrieve(session_id)
    except StripeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid checkout session.",
        ) from exc

    metadata = getattr(session, "metadata", None) or {}
    if metadata.get("user_id") != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session does not belong to this user.",
        )

    payment_status = getattr(session, "payment_status", None)
    return {
        "verified": payment_status in {"paid", "no_payment_required"},
        "payment_status": payment_status,
    }


@router.get("/status", response_model=StripeStatusResponse)
async def get_stripe_status() -> StripeStatusResponse:
    """Return page-buying availability for frontend feature gating."""
    return StripeStatusResponse(page_buying_enabled=config.STRIPE_PAGE_BUYING_ENABLED)


@router.post("/webhook", response_model=StripeWebhookResponse)
async def stripe_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
) -> StripeWebhookResponse:
    """Handle Stripe webhooks and grant purchased pages after payment."""
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

    logger.info("Received Stripe webhook event: %s", event.type)

    # --- Checkout session events ---
    if event.type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        checkout_session = event.data.object
        payment_status = getattr(checkout_session, "payment_status", None)
        session_mode = str(getattr(checkout_session, "mode", "payment")).lower()

        if event.type == "checkout.session.completed" and payment_status not in {
            "paid",
            "no_payment_required",
        }:
            logger.info(
                "Received checkout.session.completed for unpaid session %s; waiting for async success.",
                checkout_session.id,
            )
            return StripeWebhookResponse()

        if session_mode == "subscription":
            return await _activate_subscription_from_checkout(
                db_session, checkout_session
            )

        return await _fulfill_completed_purchase(db_session, checkout_session)

    if event.type in {
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    }:
        checkout_session = event.data.object
        # Only PAYG purchases have a PagePurchase row; subscription sessions are ignored here.
        if str(getattr(checkout_session, "mode", "payment")).lower() != "subscription":
            return await _mark_purchase_failed(db_session, str(checkout_session.id))
        return StripeWebhookResponse()

    # --- Subscription lifecycle events ---
    if event.type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        subscription = event.data.object
        return await _handle_subscription_event(db_session, subscription)

    # --- Invoice events ---
    if event.type == "invoice.payment_succeeded":
        invoice = event.data.object
        return await _handle_invoice_payment_succeeded(db_session, invoice)

    if event.type == "invoice.payment_failed":
        invoice = event.data.object
        return await _handle_invoice_payment_failed(db_session, invoice)

    logger.info("Unhandled Stripe event type: %s", event.type)
    return StripeWebhookResponse()


@router.get("/purchases", response_model=PagePurchaseHistoryResponse)
async def get_page_purchases(
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
    offset: int = 0,
    limit: int = 50,
) -> PagePurchaseHistoryResponse:
    """Return the authenticated user's page-purchase history."""
    limit = min(limit, 100)
    purchases = (
        (
            await db_session.execute(
                select(PagePurchase)
                .where(PagePurchase.user_id == user.id)
                .order_by(PagePurchase.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return PagePurchaseHistoryResponse(purchases=purchases)
