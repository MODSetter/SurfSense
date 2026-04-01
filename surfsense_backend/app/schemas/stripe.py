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
