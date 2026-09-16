"""Reading a Stripe checkout session for what it says about a license."""

from __future__ import annotations

import contextlib
from typing import Any, cast

from app.config import config
from app.license.email.address import normalize_email
from app.license.keygen import LicensePlan
from app.license.models import LicenseIssueError


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


def _line_items(checkout_session: Any, *, stripe_client: Any) -> list[Any]:
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
    expanded = stripe_client.v1.checkout.sessions.retrieve(
        session_id, params={"expand": ["line_items"]}
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


def resolve_license_plan(
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
    """
    metadata = _metadata_of(checkout_session)
    if metadata.get("purchase_type") == "license":
        raw_plan = metadata.get("plan")
        if raw_plan not in {"individual", "team"}:
            raise LicenseIssueError(f"Unsupported license plan: {raw_plan!r}")
        plan = cast(LicensePlan, raw_plan)
        if plan != "team":
            return plan, None
        try:
            quantity = int(metadata["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise LicenseIssueError("Team license quantity must be an integer") from exc
        if quantity < 1:
            raise LicenseIssueError("Team license quantity must be at least 1")
        return plan, quantity

    individual_price = config.STRIPE_PRICE_LICENSE_INDIVIDUAL
    team_price = config.STRIPE_PRICE_LICENSE_TEAM
    if not (individual_price or team_price):
        return None

    for line_item in _line_items(checkout_session, stripe_client=stripe_client):
        price_id = _price_id(line_item)
        if individual_price and price_id == individual_price:
            return "individual", None
        if team_price and price_id == team_price:
            quantity = int(getattr(line_item, "quantity", 0) or 0)
            if quantity < 1:
                raise LicenseIssueError("Team license quantity must be at least 1")
            return "team", quantity
    return None
