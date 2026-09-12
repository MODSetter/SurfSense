"""Issue and persist Keygen-backed offline licenses."""

from __future__ import annotations

from typing import Any, Literal, cast

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import LicensePurchase
from app.services import keygen
from app.services.keygen import LicensePlan

LicenseSource = Literal["stripe", "trial", "enterprise"]
_PAID_STATUSES = {"paid", "no_payment_required"}


def _metadata_of(checkout_session: Any) -> dict[str, str]:
    metadata = getattr(checkout_session, "metadata", None)
    if isinstance(metadata, dict):
        return {str(key): str(value) for key, value in metadata.items()}
    to_dict = getattr(metadata, "to_dict", None)
    if callable(to_dict):
        return {str(key): str(value) for key, value in to_dict(recursive=False).items()}
    return {}


def _customer_email(checkout_session: Any) -> str:
    details = getattr(checkout_session, "customer_details", None)
    email = (
        details.get("email")
        if isinstance(details, dict)
        else getattr(details, "email", None)
    )
    if not email or not str(email).strip():
        raise ValueError("License checkout session has no customer email")
    return str(email).strip().lower()


async def issue_license(
    session: AsyncSession,
    *,
    plan: LicensePlan,
    email: str,
    max_users: int | None = None,
    source: LicenseSource,
    stripe_session_id: str | None = None,
) -> LicensePurchase:
    """Create and check out one Keygen license, then stage its stored file."""
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("License email is required")
    if plan != "team":
        max_users = None

    keygen_license_id = await keygen.create_license(
        plan,
        normalized_email,
        max_users,
    )
    certificate = await keygen.checkout_license(keygen_license_id)
    purchase = LicensePurchase(
        stripe_checkout_session_id=stripe_session_id,
        email=normalized_email,
        plan=plan,
        max_users=max_users,
        source=source,
        keygen_license_id=keygen_license_id,
        certificate=certificate,
    )
    session.add(purchase)
    await session.flush()
    return purchase


async def fulfill_license_session(
    session: AsyncSession,
    checkout_session: Any,
) -> LicensePurchase:
    """Idempotently issue the license represented by a paid Stripe session."""
    metadata = _metadata_of(checkout_session)
    if metadata.get("purchase_type") != "license":
        raise ValueError("Checkout session is not a license purchase")
    if getattr(checkout_session, "payment_status", None) not in _PAID_STATUSES:
        raise ValueError("License checkout session is not paid")

    stripe_session_id = str(getattr(checkout_session, "id", "")).strip()
    if not stripe_session_id:
        raise ValueError("License checkout session id is required")

    # Serialize webhook and success-page races before making the external call.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"license-session:{stripe_session_id}"},
    )
    existing = (
        await session.execute(
            select(LicensePurchase).where(
                LicensePurchase.stripe_checkout_session_id == stripe_session_id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        await session.commit()
        return existing

    raw_plan = metadata.get("plan")
    if raw_plan not in {"individual", "team"}:
        raise ValueError(f"Unsupported license plan: {raw_plan!r}")
    plan = cast(LicensePlan, raw_plan)

    max_users = None
    if plan == "team":
        try:
            max_users = int(metadata["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Team license quantity must be an integer") from exc
        if max_users < 1:
            raise ValueError("Team license quantity must be at least 1")

    purchase = await issue_license(
        session,
        plan=plan,
        email=_customer_email(checkout_session),
        max_users=max_users,
        source="stripe",
        stripe_session_id=stripe_session_id,
    )
    await session.commit()
    return purchase
