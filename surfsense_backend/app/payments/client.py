"""The Stripe client and the object plumbing every caller needs."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from stripe import StripeClient

from app.config import config
from app.db import User

logger = logging.getLogger(__name__)


def get_stripe_client() -> StripeClient:
    """Return a configured Stripe client or raise if Stripe is disabled."""
    if not config.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe checkout is not configured.",
        )
    return StripeClient(config.STRIPE_SECRET_KEY)


def normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "id", str(value))


def get_metadata(checkout_session: Any) -> dict[str, str]:
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


async def get_or_create_stripe_customer(
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
