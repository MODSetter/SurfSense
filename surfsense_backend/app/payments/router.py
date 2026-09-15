"""HTTP surface for buying credit and managing auto-reload."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeError

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    CreditPurchase,
    CreditPurchaseStatus,
    PagePurchase,
    User,
    get_async_session,
)
from app.users import require_session_context

from . import auto_reload, credits
from .client import (
    get_or_create_stripe_customer,
    get_stripe_client,
    normalize_optional_string,
)
from .schemas import (
    AutoReloadSettingsResponse,
    CreateAutoReloadSetupSessionRequest,
    CreateAutoReloadSetupSessionResponse,
    CreateCreditCheckoutSessionRequest,
    CreateCreditCheckoutSessionResponse,
    CreditPurchaseHistoryResponse,
    CreditStripeStatusResponse,
    FinalizeCheckoutResponse,
    PagePurchaseHistoryResponse,
    UpdateAutoReloadSettingsRequest,
)
from .webhook import router as webhook_router

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe"])
router.include_router(webhook_router)


@router.post(
    "/create-credit-checkout-session",
    response_model=CreateCreditCheckoutSessionResponse,
)
async def create_credit_checkout_session(
    body: CreateCreditCheckoutSessionRequest,
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> CreateCreditCheckoutSessionResponse:
    """Create a Stripe Checkout Session for buying credit packs.

    Each pack grants ``STRIPE_CREDIT_MICROS_PER_UNIT`` micro-USD of credit
    (default 1_000_000 = $1.00). The balance is debited at the actual provider
    cost reported by LiteLLM (premium calls) or ``MICROS_PER_PAGE`` per page
    (ETL), so $1 of credit always buys $1 worth of usage at cost.
    """
    user = auth.user
    credits.ensure_credit_buying_enabled()
    stripe_client = get_stripe_client()
    price_id = credits.get_required_credit_price_id()
    success_url, cancel_url = credits.get_checkout_urls(body.workspace_id)
    credit_micros_granted = body.quantity * config.STRIPE_CREDIT_MICROS_PER_UNIT

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
                    "credit_micros_per_unit": str(config.STRIPE_CREDIT_MICROS_PER_UNIT),
                    "purchase_type": "credits",
                },
            }
        )
    except StripeError as exc:
        logger.exception(
            "Failed to create credit checkout session for user %s", user.id
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
        CreditPurchase(
            user_id=user.id,
            stripe_checkout_session_id=str(checkout_session.id),
            stripe_payment_intent_id=normalize_optional_string(
                getattr(checkout_session, "payment_intent", None)
            ),
            quantity=body.quantity,
            credit_micros_granted=credit_micros_granted,
            amount_total=getattr(checkout_session, "amount_total", None),
            currency=getattr(checkout_session, "currency", None),
            source="checkout",
            status=CreditPurchaseStatus.PENDING,
        )
    )
    await db_session.commit()

    return CreateCreditCheckoutSessionResponse(checkout_url=checkout_url)


@router.get("/finalize-checkout", response_model=FinalizeCheckoutResponse)
async def finalize_checkout(
    session_id: str,
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> FinalizeCheckoutResponse:
    """Synchronously fulfil a credit checkout session from the success page.

    Solves the webhook-vs-redirect race: the user lands on
    ``/dashboard/<id>/purchase-success?session_id=cs_...`` typically a
    few hundred ms after paying, but Stripe's ``checkout.session.completed``
    webhook can take 5-30s+ to arrive. Calling this endpoint on success-page
    mount fulfils the purchase immediately via the same idempotent helper the
    webhook uses.

    Authorization: the session's ``client_reference_id`` must match the
    authenticated user's id.
    """
    user = auth.user
    stripe_client = get_stripe_client()

    try:
        checkout_session = stripe_client.v1.checkout.sessions.retrieve(session_id)
    except StripeError as exc:
        logger.warning(
            "finalize_checkout: stripe lookup failed for session=%s user=%s: %s",
            session_id,
            user.id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkout session not found.",
        ) from exc

    client_reference_id = getattr(checkout_session, "client_reference_id", None)
    if client_reference_id != str(user.id):
        logger.warning(
            "finalize_checkout: ownership mismatch session=%s client_ref=%s user=%s",
            session_id,
            client_reference_id,
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This checkout session does not belong to you.",
        )

    payment_status = getattr(checkout_session, "payment_status", None)
    session_status = getattr(checkout_session, "status", None)
    is_paid = payment_status in {"paid", "no_payment_required"}
    is_expired = session_status == "expired"

    if is_paid:
        await credits.fulfill_completed_credit_purchase(db_session, checkout_session)
    elif is_expired:
        await credits.mark_credit_purchase_failed(db_session, str(checkout_session.id))
    # Otherwise leave the row alone — frontend keeps polling and the webhook
    # will eventually win the race.

    await db_session.refresh(user)

    purchase = (
        await db_session.execute(
            select(CreditPurchase).where(
                CreditPurchase.stripe_checkout_session_id == str(checkout_session.id)
            )
        )
    ).scalar_one_or_none()
    return FinalizeCheckoutResponse(
        status=purchase.status.value if purchase else "pending",
        credit_micros_balance=user.credit_micros_balance,
        credit_micros_granted=(purchase.credit_micros_granted if purchase else None),
    )


@router.get("/credit-status", response_model=CreditStripeStatusResponse)
async def get_credit_status(
    auth: AuthContext = Depends(require_session_context),
) -> CreditStripeStatusResponse:
    """Return credit-buying availability and current balance for the frontend.

    ``credit_micros_balance`` is in micro-USD (1_000_000 = $1.00); the FE
    divides by 1M when displaying.
    """
    user = auth.user
    return CreditStripeStatusResponse(
        credit_buying_enabled=config.STRIPE_CREDIT_BUYING_ENABLED,
        credit_micros_balance=user.credit_micros_balance,
    )


@router.get("/credit-purchases", response_model=CreditPurchaseHistoryResponse)
async def get_credit_purchases(
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
    offset: int = 0,
    limit: int = 50,
) -> CreditPurchaseHistoryResponse:
    """Return the authenticated user's credit purchase history."""
    user = auth.user
    limit = min(limit, 100)
    purchases = (
        (
            await db_session.execute(
                select(CreditPurchase)
                .where(CreditPurchase.user_id == user.id)
                .order_by(CreditPurchase.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return CreditPurchaseHistoryResponse(purchases=purchases)


@router.get("/purchases", response_model=PagePurchaseHistoryResponse)
async def get_page_purchases(
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
    offset: int = 0,
    limit: int = 50,
) -> PagePurchaseHistoryResponse:
    """Return the authenticated user's legacy page-purchase history (read-only).

    Page buying is removed; this endpoint stays for historical records.
    """
    user = auth.user
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


@router.post(
    "/auto-reload/setup",
    response_model=CreateAutoReloadSetupSessionResponse,
)
async def create_auto_reload_setup_session(
    body: CreateAutoReloadSetupSessionRequest,
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> CreateAutoReloadSetupSessionResponse:
    """Start a ``mode=setup`` checkout session to save a card for auto-reload.

    Uses a SetupIntent (no immediate charge) attached to the user's Stripe
    Customer so the card can later be charged off-session. On completion the
    webhook stores the resulting payment method on the user.
    """
    user = auth.user
    auto_reload.ensure_auto_reload_enabled()
    credits.ensure_credit_buying_enabled()
    stripe_client = get_stripe_client()
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    customer_id = await get_or_create_stripe_customer(stripe_client, db_session, user)

    base_url = config.NEXT_FRONTEND_URL.rstrip("/")
    success_url = (
        f"{base_url}/dashboard/{body.workspace_id}/user-settings/purchases"
        f"?auto_reload_setup=success"
    )
    cancel_url = (
        f"{base_url}/dashboard/{body.workspace_id}/user-settings/purchases"
        f"?auto_reload_setup=cancel"
    )

    try:
        checkout_session = stripe_client.v1.checkout.sessions.create(
            params={
                "mode": "setup",
                # Required in setup mode when payment_method_types is omitted
                # (dynamic payment methods); auto-reload charges are in USD.
                "currency": "usd",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "customer": customer_id,
                "client_reference_id": str(user.id),
                "metadata": {
                    "user_id": str(user.id),
                    "purchase_type": "auto_reload_setup",
                },
            }
        )
    except StripeError as exc:
        logger.exception(
            "Failed to create auto-reload setup session for user %s", user.id
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create Stripe setup session.",
        ) from exc

    checkout_url = getattr(checkout_session, "url", None)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe setup session did not return a URL.",
        )

    return CreateAutoReloadSetupSessionResponse(checkout_url=checkout_url)


@router.get("/auto-reload", response_model=AutoReloadSettingsResponse)
async def get_auto_reload_settings(
    auth: AuthContext = Depends(require_session_context),
) -> AutoReloadSettingsResponse:
    """Return the user's auto-reload configuration and saved-card state."""
    return auto_reload.settings_response(auth.user)


@router.put("/auto-reload", response_model=AutoReloadSettingsResponse)
async def update_auto_reload_settings(
    body: UpdateAutoReloadSettingsRequest,
    auth: AuthContext = Depends(require_session_context),
    db_session: AsyncSession = Depends(get_async_session),
) -> AutoReloadSettingsResponse:
    """Update auto-reload preferences.

    Enabling requires a saved card plus a positive threshold and an amount of
    at least ``AUTO_RELOAD_MIN_AMOUNT_MICROS``. Disabling always succeeds and
    clears any prior failure flag.
    """
    user = auth.user
    auto_reload.ensure_auto_reload_enabled()

    locked = (
        (
            await db_session.execute(
                select(User).where(User.id == user.id).with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one()
    )

    if body.enabled:
        if not locked.auto_reload_payment_method_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Add a payment method before enabling auto-reload.",
            )
        if not body.threshold_micros or body.threshold_micros <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A positive low-balance threshold is required.",
            )
        if (
            body.amount_micros is None
            or body.amount_micros < config.AUTO_RELOAD_MIN_AMOUNT_MICROS
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Reload amount must be at least "
                    f"{config.AUTO_RELOAD_MIN_AMOUNT_MICROS} micro-USD."
                ),
            )
        locked.auto_reload_enabled = True
        locked.auto_reload_threshold_micros = body.threshold_micros
        locked.auto_reload_amount_micros = body.amount_micros
        # Re-enabling clears the prior failure flag so the user can retry.
        locked.auto_reload_failed_at = None
    else:
        locked.auto_reload_enabled = False
        if body.threshold_micros is not None:
            locked.auto_reload_threshold_micros = body.threshold_micros
        if body.amount_micros is not None:
            locked.auto_reload_amount_micros = body.amount_micros

    await db_session.commit()
    await db_session.refresh(locked)
    return auto_reload.settings_response(locked)
