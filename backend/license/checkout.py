"""Reading a Stripe checkout session for what it says about a license."""

from __future__ import annotations

import contextlib
from functools import partial
from typing import Any, cast

import anyio

from license.email.address import normalize_email
from license.keygen import COUNTED_PLANS, LicensePlan
from license.models import LicenseIssueError
from license.settings import config


def _metadata_of(obj: Any) -> dict[str, str]:
    metadata = getattr(obj, "metadata", None)
    if isinstance(metadata, dict):
        return {str(key): str(value) for key, value in metadata.items()}
    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        return {str(key): str(value) for key, value in to_dict(recursive=False).items()}
    return {}


def customer_email(checkout_session: Any) -> str:
    details = getattr(checkout_session, "customer_details", None)
    email = (
        details.get("email")
        if isinstance(details, dict)
        else getattr(details, "email", None)
    )
    if not email or not str(email).strip():
        raise LicenseIssueError("License checkout session has no customer email")
    return normalize_email(str(email))


def customer_id(checkout_session: Any) -> str | None:
    customer = getattr(checkout_session, "customer", None)
    if isinstance(customer, str):
        return customer or None
    return str(getattr(customer, "id", "")) or None


def subscription_id(checkout_session: Any) -> str | None:
    """The subscription a subscription-mode checkout started, or ``None``."""
    subscription = getattr(checkout_session, "subscription", None)
    if isinstance(subscription, str):
        return subscription or None
    return str(getattr(subscription, "id", "") or "") or None


# The Payment Link's custom text field; Stripe allows only alphanumeric keys.
FIRM_FIELD_KEY = "firm"
_FIRM_MAX_LENGTH = 120


def _field(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def firm_name(checkout_session: Any) -> str | None:
    """The firm's name as typed at checkout, tidied, or ``None`` when left out.

    Never a reason to refuse a purchase: the job screens fall back to the address.
    """
    for custom_field in getattr(checkout_session, "custom_fields", None) or []:
        if _field(custom_field, "key") != FIRM_FIELD_KEY:
            continue
        value = _field(_field(custom_field, "text") or {}, "value")
        name = " ".join(str(value or "").split())[:_FIRM_MAX_LENGTH]
        return name or None
    return None


async def _line_items(checkout_session: Any, *, stripe_client: Any) -> list[Any]:
    """Line items for the session, fetching them if Stripe did not expand them.

    Webhook payloads never carry line items, so a Payment Link purchase needs
    one extra call to learn which price was bought.
    """
    existing = getattr(checkout_session, "line_items", None)
    data = getattr(existing, "data", None) if existing is not None else None
    if data:
        return list(data)
    if stripe_client is None:
        return []

    session_id = str(getattr(checkout_session, "id", "") or "")
    if not session_id:
        return []
    # In a thread: the event loop also streams every plugin call.
    expanded = await anyio.to_thread.run_sync(
        partial(
            stripe_client.v1.checkout.sessions.retrieve,
            session_id,
            params={"expand": ["line_items"]},
        )
    )
    items = getattr(expanded, "line_items", None)
    # Cache onto the session: the webhook classifies a session and then
    # fulfils it, and without this a Payment Link purchase pays for the same
    # lookup twice.
    with contextlib.suppress(AttributeError, TypeError):
        checkout_session.line_items = items
    return list(getattr(items, "data", None) or [])


def _price_id(line_item: Any) -> str:
    price = getattr(line_item, "price", None)
    if isinstance(price, str):
        return price
    return str(getattr(price, "id", "") or "")


async def resolve_license_plan(
    checkout_session: Any,
    *,
    stripe_client: Any = None,
) -> tuple[LicensePlan, int | None] | None:
    """Work out which license a paid session bought, or ``None`` if it is not one.

    Two sources, in order:

    1. Session metadata (``plan`` / ``quantity``), set by an API-created
       checkout session.
    2. The line item's price ID, matched against the configured license
       prices. Payment Links carry no session metadata, and supporting both
       means the Payment-Link-vs-API decision never blocks this code.

    The count is a team's seats or a Business license's people.
    """
    metadata = _metadata_of(checkout_session)
    if metadata.get("purchase_type") == "license":
        raw_plan = metadata.get("plan")
        if raw_plan not in {"individual", "team", "business"}:
            raise LicenseIssueError(f"Unsupported license plan: {raw_plan!r}")
        plan = cast(LicensePlan, raw_plan)
        if plan not in COUNTED_PLANS:
            return plan, None
        try:
            quantity = int(metadata["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LicenseIssueError(
                f"{plan.title()} license quantity must be an integer"
            ) from exc
        return plan, _at_least_one(plan, quantity)

    prices: dict[str, LicensePlan] = {
        price: plan
        for price, plan in (
            (config.STRIPE_PRICE_LICENSE_INDIVIDUAL, "individual"),
            (config.STRIPE_PRICE_LICENSE_TEAM, "team"),
            (config.STRIPE_PRICE_LICENSE_BUSINESS, "business"),
        )
        if price
    }
    if not prices:
        return None

    for line_item in await _line_items(checkout_session, stripe_client=stripe_client):
        plan = prices.get(_price_id(line_item))
        if plan is None:
            continue
        if plan not in COUNTED_PLANS:
            return plan, None
        quantity = int(getattr(line_item, "quantity", 0) or 0)
        return plan, _at_least_one(plan, quantity)
    return None


def license_prices_configured() -> bool:
    """Whether any price can name a plan; without one no line item is fetched."""
    return bool(
        config.STRIPE_PRICE_LICENSE_INDIVIDUAL
        or config.STRIPE_PRICE_LICENSE_TEAM
        or config.STRIPE_PRICE_LICENSE_BUSINESS
    )


def _at_least_one(plan: LicensePlan, quantity: int) -> int:
    if quantity < 1:
        raise LicenseIssueError(f"{plan.title()} license quantity must be at least 1")
    return quantity
