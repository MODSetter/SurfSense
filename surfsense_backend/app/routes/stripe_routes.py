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
    FinalizeCheckoutResponse,
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
    # Stripe substitutes ``{CHECKOUT_SESSION_ID}`` with the actual session id
    # at redirect time. The frontend uses it to call /stripe/finalize-checkout
    # which fulfils synchronously without waiting for the webhook — fixing the
    # webhook-vs-redirect race where users land on /purchase-success before
    # checkout.session.completed has been delivered.
    success_url = (
        f"{base_url}/dashboard/{search_space_id}/purchase-success"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
    )
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

    # 1. Plain dict (older SDKs that subclassed dict, JSON-decoded events
    #    in tests, etc.).
    if isinstance(metadata, dict):
        return {str(k): str(v) for k, v in metadata.items()}

    # 2. Modern Stripe SDK: every ``StripeObject`` has ``to_dict()``.
    #    ``recursive=False`` is correct because Stripe metadata values
    #    are always primitive strings.
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

    # 3. Last-resort: read the SDK's private ``_data`` backing dict.
    #    Stable across stripe-python 6.x -> 15.x.
    inner = getattr(metadata, "_data", None)
    if isinstance(inner, dict):
        return {str(k): str(v) for k, v in inner.items()}

    logger.warning(
        "Could not extract metadata from checkout session %s (metadata type=%s)",
        getattr(checkout_session, "id", "?"),
        type(metadata).__name__,
    )
    return {}


# Canonical purchase_type metadata values. ``premium_credit`` was emitted
# by an earlier release of ``create_token_checkout_session`` so it's still
# accepted on the read side for backward compat with in-flight sessions.
_PURCHASE_TYPE_TOKEN_VALUES = frozenset({"premium_tokens", "premium_credit"})


def _is_token_purchase(metadata: dict[str, str]) -> bool:
    """Return True for premium-credit (a.k.a. premium_token) purchases."""
    return metadata.get("purchase_type", "page_packs") in _PURCHASE_TYPE_TOKEN_VALUES


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
        # Read the new metadata key first, fall back to the legacy one so
        # in-flight checkout sessions created before the cost-credits
        # release still fulfil correctly (the unit is numerically the
        # same: $1 buys 1_000_000 micro-USD == 1_000_000 tokens).
        credit_micros_per_unit = int(
            metadata.get("credit_micros_per_unit")
            or metadata.get("tokens_per_unit", "0")
        )

        if not user_id or quantity <= 0 or credit_micros_per_unit <= 0:
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
            credit_micros_granted=quantity * credit_micros_per_unit,
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
    # Top up the user's credit balance by the granted micro-USD amount.
    # ``max(used, limit)`` clamps the case where the legacy code wrote a
    # used value above the limit (e.g. underbilling rounding) so adding
    # ``credit_micros_granted`` always lifts the limit by the full pack
    # size rather than disappearing into past overuse.
    user.premium_credit_micros_limit = (
        max(user.premium_credit_micros_used, user.premium_credit_micros_limit)
        + purchase.credit_micros_granted
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

            metadata = _get_metadata(checkout_session)
            if _is_token_purchase(metadata):
                return await _fulfill_completed_token_purchase(
                    db_session, checkout_session
                )
            return await _fulfill_completed_purchase(db_session, checkout_session)

        if event.type in {
            "checkout.session.async_payment_failed",
            "checkout.session.expired",
        }:
            checkout_session = event.data.object
            metadata = _get_metadata(checkout_session)
            if _is_token_purchase(metadata):
                return await _mark_token_purchase_failed(
                    db_session, str(checkout_session.id)
                )
            return await _mark_purchase_failed(db_session, str(checkout_session.id))
    except Exception:
        # Re-raise so FastAPI returns 500 and Stripe retries this delivery.
        # Logging here gives us a structured trail with event id + type so
        # future webhook bugs surface immediately in the logs without
        # having to grep by request_id.
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
    user: User = Depends(current_active_user),
    db_session: AsyncSession = Depends(get_async_session),
) -> FinalizeCheckoutResponse:
    """Synchronously fulfil a checkout session from the success page.

    Solves the webhook-vs-redirect race: the user lands on
    ``/dashboard/<id>/purchase-success?session_id=cs_...`` typically a
    few hundred ms after paying, but Stripe's
    ``checkout.session.completed`` webhook can take 5-30s+ to arrive.
    Calling this endpoint on success-page mount fulfils the purchase
    immediately by retrieving the session from Stripe's API and
    invoking the same idempotent helpers the webhook uses.

    Idempotency: if the webhook has already fulfilled this purchase
    (status=COMPLETED), the helpers short-circuit and we just return
    the latest balance. Concurrent webhook + finalize calls are safe
    because both acquire ``SELECT ... FOR UPDATE`` on the purchase row.

    Authorization: the session's ``client_reference_id`` must match the
    authenticated user's id. This prevents a user from finalising
    someone else's checkout session if they happen to know the id.
    """
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

    # Authorization check: the user finalising must be the user who
    # initiated the checkout. ``client_reference_id`` is set in
    # ``create_checkout_session`` / ``create_token_checkout_session``.
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

    metadata = _get_metadata(checkout_session)
    is_token = _is_token_purchase(metadata)
    payment_status = getattr(checkout_session, "payment_status", None)
    session_status = getattr(checkout_session, "status", None)

    # Defensive fallback: if metadata can't be read for any reason
    # (extraction failure, manually-created session in Stripe dashboard,
    # SDK upgrade breaking ``to_dict``, etc.) we'd otherwise route every
    # purchase to the page_packs handler and get stuck. Resolve the
    # purchase_type by checking which table actually has the row keyed
    # by this Stripe session id.
    if not metadata:
        existing_token_purchase = (
            await db_session.execute(
                select(PremiumTokenPurchase.id).where(
                    PremiumTokenPurchase.stripe_checkout_session_id
                    == str(checkout_session.id)
                )
            )
        ).scalar_one_or_none()
        if existing_token_purchase is not None:
            is_token = True
        else:
            existing_page_purchase = (
                await db_session.execute(
                    select(PagePurchase.id).where(
                        PagePurchase.stripe_checkout_session_id
                        == str(checkout_session.id)
                    )
                )
            ).scalar_one_or_none()
            if existing_page_purchase is None:
                logger.error(
                    "finalize_checkout: no purchase row in either table "
                    "and metadata is empty for session=%s user=%s",
                    session_id,
                    user.id,
                )
                # Fall through; downstream path will short-circuit on
                # missing-row + empty-metadata.
        logger.info(
            "finalize_checkout: recovered purchase_type=%s for session=%s "
            "via DB fallback (metadata was empty)",
            "premium_tokens" if is_token else "page_packs",
            session_id,
        )

    is_paid = payment_status in {"paid", "no_payment_required"}
    is_expired = session_status == "expired"

    if is_paid:
        if is_token:
            await _fulfill_completed_token_purchase(db_session, checkout_session)
        else:
            await _fulfill_completed_purchase(db_session, checkout_session)
    elif is_expired:
        if is_token:
            await _mark_token_purchase_failed(db_session, str(checkout_session.id))
        else:
            await _mark_purchase_failed(db_session, str(checkout_session.id))
    # Otherwise (e.g. payment_status="unpaid", session_status="open"),
    # leave the purchase row alone — frontend will keep polling and the
    # webhook will eventually win the race.

    # Refresh the user row so the response reflects any update applied
    # by the fulfilment helpers in this same session.
    await db_session.refresh(user)

    if is_token:
        purchase = (
            await db_session.execute(
                select(PremiumTokenPurchase).where(
                    PremiumTokenPurchase.stripe_checkout_session_id
                    == str(checkout_session.id)
                )
            )
        ).scalar_one_or_none()
        return FinalizeCheckoutResponse(
            purchase_type="premium_tokens",
            status=purchase.status.value if purchase else "pending",
            premium_credit_micros_limit=user.premium_credit_micros_limit,
            premium_credit_micros_used=user.premium_credit_micros_used,
            premium_credit_micros_granted=(
                purchase.credit_micros_granted if purchase else None
            ),
        )

    purchase = (
        await db_session.execute(
            select(PagePurchase).where(
                PagePurchase.stripe_checkout_session_id == str(checkout_session.id)
            )
        )
    ).scalar_one_or_none()
    return FinalizeCheckoutResponse(
        purchase_type="page_packs",
        status=purchase.status.value if purchase else "pending",
        pages_limit=user.pages_limit,
        pages_used=user.pages_used,
        pages_granted=purchase.pages_granted if purchase else None,
    )


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
    # See ``_get_checkout_urls`` for why session_id is appended.
    success_url = (
        f"{base_url}/dashboard/{search_space_id}/purchase-success"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
    )
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
    """Create a Stripe Checkout Session for buying premium credit packs.

    Each pack grants ``STRIPE_CREDIT_MICROS_PER_UNIT`` micro-USD of
    credit (default 1_000_000 = $1.00). The user's balance is debited
    at the actual provider cost reported by LiteLLM at finalize time,
    so $1 of credit always buys $1 worth of provider usage at cost.
    """
    _ensure_token_buying_enabled()
    stripe_client = get_stripe_client()
    price_id = _get_required_token_price_id()
    success_url, cancel_url = _get_token_checkout_urls(body.search_space_id)
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
                    # Canonical value matched by ``_is_token_purchase``.
                    # The legacy ``"premium_credit"`` is still accepted on
                    # the read side for any in-flight sessions started
                    # before this rename.
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
            credit_micros_granted=credit_micros_granted,
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
    """Return token-buying availability and current premium credit quota for frontend.

    Values are in micro-USD (1_000_000 = $1.00); the FE divides by 1M
    when displaying. The route name is preserved for back-compat with
    pinned client deployments.
    """
    used = user.premium_credit_micros_used
    limit = user.premium_credit_micros_limit
    return TokenStripeStatusResponse(
        token_buying_enabled=config.STRIPE_TOKEN_BUYING_ENABLED,
        premium_credit_micros_used=used,
        premium_credit_micros_limit=limit,
        premium_credit_micros_remaining=max(0, limit - used),
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
