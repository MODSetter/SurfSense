"""Stripe routes for pay-as-you-go page purchases."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import SignatureVerificationError, StripeClient, StripeError

from app.config import config
from app.db import (
    PagePurchase,
    PagePurchaseStatus,
    PremiumTokenPurchase,
    PremiumTokenPurchaseStatus,
    User,
    get_async_session,
)
from app.schemas.stripe import (
    CreateCheckoutSessionRequest,
    CreateCheckoutSessionResponse,
    CreateTokenCheckoutSessionRequest,
    CreateTokenCheckoutSessionResponse,
    PagePurchaseHistoryResponse,
    StripeStatusResponse,
    StripeWebhookResponse,
    TokenPurchaseHistoryResponse,
    TokenStripeStatusResponse,
)
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])


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


async def _mark_token_purchase_failed(
    db_session: AsyncSession, checkout_session_id: str
) -> StripeWebhookResponse:
    purchase = (
        await db_session.execute(
            select(PremiumTokenPurchase)
            .where(
                PremiumTokenPurchase.stripe_checkout_session_id == checkout_session_id
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is not None and purchase.status == PremiumTokenPurchaseStatus.PENDING:
        purchase.status = PremiumTokenPurchaseStatus.FAILED
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


async def _fulfill_completed_token_purchase(
    db_session: AsyncSession, checkout_session: Any
) -> StripeWebhookResponse:
    """Grant premium tokens to the user after a confirmed Stripe payment."""
    checkout_session_id = str(checkout_session.id)
    purchase = (
        await db_session.execute(
            select(PremiumTokenPurchase)
            .where(
                PremiumTokenPurchase.stripe_checkout_session_id == checkout_session_id
            )
            .with_for_update()
        )
    ).scalar_one_or_none()

    if purchase is None:
        metadata = _get_metadata(checkout_session)
        user_id = metadata.get("user_id")
        quantity = int(metadata.get("quantity", "0"))
        tokens_per_unit = int(metadata.get("tokens_per_unit", "0"))

        if not user_id or quantity <= 0 or tokens_per_unit <= 0:
            logger.error(
                "Skipping token fulfillment for session %s: incomplete metadata %s",
                checkout_session_id,
                metadata,
            )
            return StripeWebhookResponse()

        purchase = PremiumTokenPurchase(
            user_id=uuid.UUID(user_id),
            stripe_checkout_session_id=checkout_session_id,
            stripe_payment_intent_id=_normalize_optional_string(
                getattr(checkout_session, "payment_intent", None)
            ),
            quantity=quantity,
            tokens_granted=quantity * tokens_per_unit,
            amount_total=getattr(checkout_session, "amount_total", None),
            currency=getattr(checkout_session, "currency", None),
            status=PremiumTokenPurchaseStatus.PENDING,
        )
        db_session.add(purchase)
        await db_session.flush()

    if purchase.status == PremiumTokenPurchaseStatus.COMPLETED:
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
            "Skipping token fulfillment for session %s: user %s not found",
            purchase.stripe_checkout_session_id,
            purchase.user_id,
        )
        return StripeWebhookResponse()

    purchase.status = PremiumTokenPurchaseStatus.COMPLETED
    purchase.completed_at = datetime.now(UTC)
    purchase.amount_total = getattr(checkout_session, "amount_total", None)
    purchase.currency = getattr(checkout_session, "currency", None)
    purchase.stripe_payment_intent_id = _normalize_optional_string(
        getattr(checkout_session, "payment_intent", None)
    )
    user.premium_tokens_limit = (
        max(user.premium_tokens_used, user.premium_tokens_limit)
        + purchase.tokens_granted
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

    if event.type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        checkout_session = event.data.object
        payment_status = getattr(checkout_session, "payment_status", None)

        if event.type == "checkout.session.completed" and payment_status not in {
            "paid",
            "no_payment_required",
        }:
            logger.info(
                "Received checkout.session.completed for unpaid session %s; waiting for async success.",
                checkout_session.id,
            )
            return StripeWebhookResponse()

        metadata = _get_metadata(checkout_session)
        purchase_type = metadata.get("purchase_type", "page_packs")
        if purchase_type == "premium_tokens":
            return await _fulfill_completed_token_purchase(db_session, checkout_session)
        return await _fulfill_completed_purchase(db_session, checkout_session)

    if event.type in {
        "checkout.session.async_payment_failed",
        "checkout.session.expired",
    }:
        checkout_session = event.data.object
        metadata = _get_metadata(checkout_session)
        purchase_type = metadata.get("purchase_type", "page_packs")
        if purchase_type == "premium_tokens":
            return await _mark_token_purchase_failed(
                db_session, str(checkout_session.id)
            )
        return await _mark_purchase_failed(db_session, str(checkout_session.id))

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


# =============================================================================
# Premium Token Purchase Routes
# =============================================================================


def _ensure_token_buying_enabled() -> None:
    if not config.STRIPE_TOKEN_BUYING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Premium token purchases are temporarily unavailable.",
        )


def _get_token_checkout_urls(search_space_id: int) -> tuple[str, str]:
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = f"{base_url}/dashboard/{search_space_id}/purchase-success"
    cancel_url = f"{base_url}/dashboard/{search_space_id}/purchase-cancel"
    return success_url, cancel_url


def _get_required_token_price_id() -> str:
    if not config.STRIPE_PREMIUM_TOKEN_PRICE_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_PREMIUM_TOKEN_PRICE_ID is not configured.",
        )
    return config.STRIPE_PREMIUM_TOKEN_PRICE_ID


@router.post("/create-token-checkout-session")
async def create_token_checkout_session(
    body: CreateTokenCheckoutSessionRequest,
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
):
    """Create a Stripe Checkout Session for buying premium token packs."""
    _ensure_token_buying_enabled()
    stripe_client = get_stripe_client()
    price_id = _get_required_token_price_id()
    success_url, cancel_url = _get_token_checkout_urls(body.search_space_id)
    tokens_granted = body.quantity * config.STRIPE_TOKENS_PER_UNIT

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
                    "tokens_per_unit": str(config.STRIPE_TOKENS_PER_UNIT),
                    "purchase_type": "premium_tokens",
                },
            }
        )
    except StripeError as exc:
        logger.exception("Failed to create token checkout session for user %s", user.id)
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
        PremiumTokenPurchase(
            user_id=user.id,
            stripe_checkout_session_id=str(checkout_session.id),
            stripe_payment_intent_id=_normalize_optional_string(
                getattr(checkout_session, "payment_intent", None)
            ),
            quantity=body.quantity,
            tokens_granted=tokens_granted,
            amount_total=getattr(checkout_session, "amount_total", None),
            currency=getattr(checkout_session, "currency", None),
            status=PremiumTokenPurchaseStatus.PENDING,
        )
    )
    await db_session.commit()

    return CreateTokenCheckoutSessionResponse(checkout_url=checkout_url)


@router.get("/token-status")
async def get_token_status(
    user: User = Depends(current_active_user),
):
    """Return token-buying availability and current premium quota for frontend."""
    used = user.premium_tokens_used
    limit = user.premium_tokens_limit
    return TokenStripeStatusResponse(
        token_buying_enabled=config.STRIPE_TOKEN_BUYING_ENABLED,
        premium_tokens_used=used,
        premium_tokens_limit=limit,
        premium_tokens_remaining=max(0, limit - used),
    )


@router.get("/token-purchases")
async def get_token_purchases(
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
    offset: int = 0,
    limit: int = 50,
):
    """Return the authenticated user's premium token purchase history."""
    limit = min(limit, 100)
    purchases = (
        (
            await db_session.execute(
                select(PremiumTokenPurchase)
                .where(PremiumTokenPurchase.user_id == user.id)
                .order_by(PremiumTokenPurchase.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return TokenPurchaseHistoryResponse(purchases=purchases)
