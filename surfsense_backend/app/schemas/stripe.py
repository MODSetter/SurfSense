"""Schemas for Stripe-backed page purchases."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db import PagePurchaseStatus


class CreateCheckoutSessionRequest(BaseModel):
    """Request body for creating a page-purchase checkout session."""

    quantity: int = Field(ge=1, le=100)
    search_space_id: int = Field(ge=1)


class CreateCheckoutSessionResponse(BaseModel):
    """Response containing the Stripe-hosted checkout URL."""

    checkout_url: str


class StripeStatusResponse(BaseModel):
    """Response describing Stripe page-buying availability."""

    page_buying_enabled: bool


class PagePurchaseRead(BaseModel):
    """Serialized page-purchase record for purchase history."""

    id: uuid.UUID
    stripe_checkout_session_id: str
    stripe_payment_intent_id: str | None = None
    quantity: int
    pages_granted: int
    amount_total: int | None = None
    currency: str | None = None
    status: PagePurchaseStatus
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PagePurchaseHistoryResponse(BaseModel):
    """Response containing the authenticated user's page purchases."""

    purchases: list[PagePurchaseRead]


class StripeWebhookResponse(BaseModel):
    """Generic acknowledgement for Stripe webhook delivery."""

    received: bool = True


class FinalizeCheckoutResponse(BaseModel):
    """Response from /stripe/finalize-checkout.

    Returned by the success page so the UI can show the post-purchase
    balance immediately, even when the Stripe webhook hasn't been
    delivered yet. ``status`` mirrors the underlying purchase row
    (``pending`` / ``completed`` / ``failed``); the FE polls this
    endpoint until it sees ``completed`` or a final ``failed``.
    """

    purchase_type: str  # "page_packs" | "premium_tokens"
    status: str  # PagePurchaseStatus / PremiumTokenPurchaseStatus value
    pages_limit: int | None = None
    pages_used: int | None = None
    pages_granted: int | None = None
    premium_credit_micros_limit: int | None = None
    premium_credit_micros_used: int | None = None
    premium_credit_micros_granted: int | None = None


class CreateTokenCheckoutSessionRequest(BaseModel):
    """Request body for creating a premium token purchase checkout session."""

    quantity: int = Field(ge=1, le=100)
    search_space_id: int = Field(ge=1)


class CreateTokenCheckoutSessionResponse(BaseModel):
    """Response containing the Stripe-hosted checkout URL."""

    checkout_url: str


class TokenPurchaseRead(BaseModel):
    """Serialized premium credit purchase record.

    ``credit_micros_granted`` is in micro-USD (1_000_000 = $1.00). The
    schema name kept ``Token`` for API back-compat with pinned clients.
    """

    id: uuid.UUID
    stripe_checkout_session_id: str
    stripe_payment_intent_id: str | None = None
    quantity: int
    credit_micros_granted: int
    amount_total: int | None = None
    currency: str | None = None
    status: str
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenPurchaseHistoryResponse(BaseModel):
    """Response containing the user's premium credit purchases."""

    purchases: list[TokenPurchaseRead]


class TokenStripeStatusResponse(BaseModel):
    """Response describing premium-credit-buying availability and balance.

    All ``premium_credit_micros_*`` fields are in micro-USD; the FE
    divides by 1_000_000 to display USD.
    """

    token_buying_enabled: bool
    premium_credit_micros_used: int = 0
    premium_credit_micros_limit: int = 0
    premium_credit_micros_remaining: int = 0
