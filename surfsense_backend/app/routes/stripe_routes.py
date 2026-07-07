"""Stripe routes for the unified credit wallet.

Buying credit packs ($1 == 1_000_000 micro-USD by default) tops up
``user.credit_micros_balance``. The same balance is debited for ETL page
processing and premium model calls. Legacy page-pack buying has been removed;
``page_purchases`` history is still readable via ``GET /stripe/purchases``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import SignatureVerificationError, StripeClient, StripeError

from app.auth.context import AuthContext
from app.config import config
from app.db import (
    CreditPurchase,
    CreditPurchaseStatus,
    PagePurchase,
    User,
    get_async_session,
)
from app.schemas.stripe import (
    AutoReloadSettingsResponse,
    CreateAutoReloadSetupSessionRequest,
    CreateAutoReloadSetupSessionResponse,
    CreateCreditCheckoutSessionRequest,
    CreateCreditCheckoutSessionResponse,
    CreditPurchaseHistoryResponse,
    CreditStripeStatusResponse,
    FinalizeCheckoutResponse,
    PagePurchaseHistoryResponse,
    StripeWebhookResponse,
    UpdateAutoReloadSettingsRequest,
)
from app.users import require_session_context

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


def _ensure_credit_buying_enabled() -> None:
    if not config.STRIPE_CREDIT_BUYING_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credit purchases are temporarily unavailable.",
        )


def _get_checkout_urls(workspace_id: int) -> tuple[str, str]:
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


def _get_required_credit_price_id() -> str:
    if not config.STRIPE_CREDIT_PRICE_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STRIPE_CREDIT_PRICE_ID is not configured.",
        )
    return config.STRIPE_CREDIT_PRICE_ID


def _ensure_auto_reload_enabled() -> None:
    if not config.AUTO_RELOAD_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Auto-reload is not available.",
        )


async def _get_or_create_stripe_customer(
    stripe_client: StripeClient, db_session: AsyncSession, user: User
) -> str:
    """Return the user's Stripe Customer id, creating + persisting one if needed.

    A Customer object is required to save and later reuse a card off-session
    (Stripe: save-and-reuse). New checkouts attach to this customer so the same
    saved card powers both manual top-ups and auto-reload.
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe_client.v1.customers.create(
        params={
            "email": user.email,
            "metadata": {"user_id": str(user.id)},
        }
    )
    customer_id = str(customer.id)

    # Persist on the live row with a lock to avoid two concurrent checkouts
    # creating duplicate customers.
    locked = (
        (
            await db_session.execute(
                select(User).where(User.id == user.id).with_for_update(of=User)
            )
        )
        .unique()
        .scalar_one_or_none()
    )
    if locked is not None:
        if locked.stripe_customer_id:
            # Another request won the race; reuse theirs.
            customer_id = locked.stripe_customer_id
        else:
            locked.stripe_customer_id = customer_id
            await db_session.commit()
    return customer_id


def _normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "id", str(value))


def _get_metadata(checkout_session: Any) -> dict[str, str]:
    """Extract checkout session metadata as a plain ``str -> str`` dict.

    In ``stripe>=15.0`` ``StripeObject`` is no longer a ``dict`` subclass
    and exposes neither ``items()`` nor ``__iter__`` nor ``keys()``.
    ``dict(obj)`` falls into the sequence protocol and raises
    ``KeyError: 0``; ``obj.items()`` raises ``AttributeError``. The
    supported way to materialize a ``StripeObject`` as a plain dict is
    its ``to_dict()`` method (added in stripe-python 8.x, present in 15.x).
    """
    metadata = getattr(checkout_session, "metadata", None)
    if metadata is None:
        return {}

    if isinstance(metadata, dict):
        return {str(k): str(v) for k, v in metadata.items()}

    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        try:
            d = to_dict(recursive=False)
            if isinstance(d, dict):
                return {str(k): str(v) for k, v in d.items()}
        except Exception:
            logger.exception(
                "Stripe metadata.to_dict() failed for session %s",
                getattr(checkout_session, "id", "?"),
            )

    inner = getattr(metadata, "_data", None)
    if isinstance(inner, dict):
        return {str(k): str(v) for k, v in inner.items()}

    logger.warning(
        "Could not extract metadata from checkout session %s (metadata type=%s)",
        getattr(checkout_session, "id", "?"),
        type(metadata).__name__,
    )
    return {}


# Canonical purchase_type metadata value is ``credits``. ``premium_tokens`` and
# ``premium_credit`` were emitted by earlier releases so they're still accepted
# on the read side for any in-flight checkout sessions.
_PURCHASE_TYPE_CREDIT_VALUES = frozenset(
    {"credits", "premium_tokens", "premium_credit"}
)


def _is_credit_purchase(metadata: dict[str, str]) -> bool:
    """Return True for a credit purchase (default for all live checkouts)."""
    return metadata.get("purchase_type", "credits") in _PURCHASE_TYPE_CREDIT_VALUES


async def _mark_credit_purchase_failed(
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


async def _fulfill_completed_credit_purchase(
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
        metadata = _get_metadata(checkout_session)
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
            stripe_payment_intent_id=_normalize_optional_string(
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
    purchase.stripe_payment_intent_id = _normalize_optional_string(
        getattr(checkout_session, "payment_intent", None)
    )
    # Add the granted micro-USD directly to the spendable wallet balance.
    user.credit_micros_balance = (
        user.credit_micros_balance + purchase.credit_micros_granted
    )

    await db_session.commit()
    return StripeWebhookResponse()


async def _handle_setup_session_completed(
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
    metadata = _get_metadata(checkout_session)
    user_id = metadata.get("user_id")
    if not user_id:
        logger.warning(
            "Setup session %s completed without user_id metadata",
            getattr(checkout_session, "id", "?"),
        )
        return StripeWebhookResponse()

    setup_intent_id = _normalize_optional_string(
        getattr(checkout_session, "setup_intent", None)
    )
    payment_method_id: str | None = None
    if setup_intent_id:
        try:
            setup_intent = stripe_client.v1.setup_intents.retrieve(setup_intent_id)
            payment_method_id = _normalize_optional_string(
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

    customer_id = _normalize_optional_string(
        getattr(checkout_session, "customer", None)
    )
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


async def _reconcile_auto_reload_payment_intent(
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
    return StripeWebhookResponse()


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
    _ensure_credit_buying_enabled()
    stripe_client = get_stripe_client()
    price_id = _get_required_credit_price_id()
    success_url, cancel_url = _get_checkout_urls(body.workspace_id)
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
            stripe_payment_intent_id=_normalize_optional_string(
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


@router.post("/webhook", response_model=StripeWebhookResponse)
async def stripe_webhook(
    request: Request,
    db_session: AsyncSession = Depends(get_async_session),
) -> StripeWebhookResponse:
    """Handle Stripe webhooks and grant purchased credit after payment."""
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

            # mode=setup sessions carry no line items / payment; they save a
            # card for off-session auto-reload.
            if getattr(checkout_session, "mode", None) == "setup":
                return await _handle_setup_session_completed(
                    stripe_client, db_session, checkout_session
                )

            metadata = _get_metadata(checkout_session)
            if _is_credit_purchase(metadata):
                return await _fulfill_completed_credit_purchase(
                    db_session, checkout_session
                )
            # Legacy page-pack purchase: page buying is removed, so log and
            # ignore rather than fulfilling.
            logger.info(
                "Ignoring non-credit checkout session %s (purchase_type=%s); "
                "page buying is removed.",
                getattr(checkout_session, "id", "?"),
                metadata.get("purchase_type"),
            )
            return StripeWebhookResponse()

        if event.type == "payment_intent.succeeded":
            return await _reconcile_auto_reload_payment_intent(
                db_session, event.data.object, succeeded=True
            )

        if event.type == "payment_intent.payment_failed":
            return await _reconcile_auto_reload_payment_intent(
                db_session, event.data.object, succeeded=False
            )

        if event.type in {
            "checkout.session.async_payment_failed",
            "checkout.session.expired",
        }:
            checkout_session = event.data.object
            metadata = _get_metadata(checkout_session)
            if _is_credit_purchase(metadata):
                return await _mark_credit_purchase_failed(
                    db_session, str(checkout_session.id)
                )
            return StripeWebhookResponse()
    except Exception:
        logger.exception(
            "Stripe webhook handler failed for event id=%s type=%s — Stripe will retry",
            getattr(event, "id", "?"),
            getattr(event, "type", "?"),
        )
        raise

    return StripeWebhookResponse()


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
        await _fulfill_completed_credit_purchase(db_session, checkout_session)
    elif is_expired:
        await _mark_credit_purchase_failed(db_session, str(checkout_session.id))
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


def _auto_reload_settings_response(user: User) -> AutoReloadSettingsResponse:
    return AutoReloadSettingsResponse(
        feature_enabled=config.AUTO_RELOAD_ENABLED,
        enabled=bool(user.auto_reload_enabled),
        threshold_micros=user.auto_reload_threshold_micros,
        amount_micros=user.auto_reload_amount_micros,
        min_amount_micros=config.AUTO_RELOAD_MIN_AMOUNT_MICROS,
        has_payment_method=bool(user.auto_reload_payment_method_id),
        failed_at=user.auto_reload_failed_at,
    )


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
    _ensure_auto_reload_enabled()
    _ensure_credit_buying_enabled()
    stripe_client = get_stripe_client()
    if not config.NEXT_FRONTEND_URL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NEXT_FRONTEND_URL is not configured.",
        )
    customer_id = await _get_or_create_stripe_customer(stripe_client, db_session, user)

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
    user = auth.user
    return _auto_reload_settings_response(user)


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
    _ensure_auto_reload_enabled()

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
    return _auto_reload_settings_response(locked)
