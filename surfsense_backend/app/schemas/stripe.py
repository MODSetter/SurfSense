"""Schemas for Stripe-backed credit purchases."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db import PagePurchaseStatus


class CreateCreditCheckoutSessionRequest(BaseModel):
    """Request body for creating a credit-purchase checkout session."""

    quantity: int = Field(ge=1, le=10_000)
    workspace_id: int = Field(ge=1)


class CreateCreditCheckoutSessionResponse(BaseModel):
    """Response containing the Stripe-hosted checkout URL."""

    checkout_url: str


class CreateSubscriptionCheckoutSessionRequest(BaseModel):
    """Request body for starting the Pro subscription checkout."""

    workspace_id: int = Field(ge=1)


class CreateSubscriptionCheckoutSessionResponse(BaseModel):
    """Response containing the Stripe-hosted subscription checkout URL."""

    checkout_url: str


class PlanStatusResponse(BaseModel):
    """The user's current plan and where they are in its allowance period.

    ``*_micros`` fields are micro-USD (1_000_000 == $1.00). ``allowance_micros``
    is what is left of this period's grant, not what the plan grants, so the UI
    can show it draining.
    """

    plan: str
    allowance_micros: int = 0
    period_end: datetime | None = None
    credit_micros_balance: int = 0
    subscription_available: bool = False


class CreditPurchaseRead(BaseModel):
    """Serialized credit purchase record.

    ``credit_micros_granted`` is in micro-USD (1_000_000 = $1.00).
    """

    id: uuid.UUID
    stripe_checkout_session_id: str
    stripe_payment_intent_id: str | None = None
    quantity: int
    credit_micros_granted: int
    amount_total: int | None = None
    currency: str | None = None
    source: str = "checkout"
    status: str
    completed_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreditPurchaseHistoryResponse(BaseModel):
    """Response containing the user's credit purchases."""

    purchases: list[CreditPurchaseRead]


class CreditStripeStatusResponse(BaseModel):
    """Response describing credit-buying availability and current funds.

    Both ``*_micros`` fields are in micro-USD; the FE divides by 1_000_000 to
    display USD. They are reported separately rather than summed because they
    behave differently — the allowance resets each period and the balance is
    permanent — but the number a user recognises as "my credit" is the sum, so
    a display that shows only one of them is wrong.
    """

    credit_buying_enabled: bool
    credit_micros_balance: int = 0
    credit_micros_allowance: int = 0
    # What the plan grants per period, as opposed to the field above, which is
    # what is *left* of it. Both are needed to say "$2.40 of $6.00", and the
    # frontend must not infer it from the plan name — the amounts are
    # environment-overridable, so a hardcoded copy would drift silently.
    allowance_granted_micros: int = 0
    allowance_period_end: datetime | None = None
    plan: str = "free"


class PagePurchaseRead(BaseModel):
    """Serialized legacy page-purchase record (read-only history)."""

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
    """Response containing the authenticated user's legacy page purchases."""

    purchases: list[PagePurchaseRead]


class AutoReloadSettingsResponse(BaseModel):
    """Auto-reload configuration + saved-card state for the settings UI.

    All ``*_micros`` fields are micro-USD (1_000_000 == $1.00). ``feature_enabled``
    reflects the server-side ``AUTO_RELOAD_ENABLED`` flag; when it is false the
    UI should hide / disable the auto-reload controls entirely.
    """

    feature_enabled: bool
    enabled: bool = False
    threshold_micros: int | None = None
    amount_micros: int | None = None
    min_amount_micros: int
    has_payment_method: bool = False
    failed_at: datetime | None = None


class UpdateAutoReloadSettingsRequest(BaseModel):
    """Update auto-reload preferences.

    Enabling requires a saved card (set up via /stripe/auto-reload/setup) plus a
    positive threshold and an amount of at least ``AUTO_RELOAD_MIN_AMOUNT_MICROS``.
    """

    enabled: bool
    threshold_micros: int | None = Field(default=None, ge=0)
    amount_micros: int | None = Field(default=None, ge=0)


class CreateAutoReloadSetupSessionRequest(BaseModel):
    """Request body for starting the save-a-card (SetupIntent) checkout."""

    workspace_id: int = Field(ge=1)


class CreateAutoReloadSetupSessionResponse(BaseModel):
    """Response containing the Stripe-hosted setup (save-card) checkout URL."""

    checkout_url: str


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

    status: str
    credit_micros_balance: int = 0
    credit_micros_granted: int | None = None
