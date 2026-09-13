"""Granting the signup credit, once per person."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import User

from .identity.registry import identities_of
from .persistence.models import SignupCreditClaim

logger = logging.getLogger(__name__)


async def award_signup_credit(session: AsyncSession, user: Any) -> int:
    """Credit a new account, once per person. Returns the micros granted."""
    if not await _try_claim(session, user):
        return 0

    granted = config.DEFAULT_CREDIT_MICROS_BALANCE
    await session.execute(
        update(User)
        .where(User.id == user.id)
        .values(credit_micros_balance=User.credit_micros_balance + granted)
    )

    return granted


async def _try_claim(session: AsyncSession, user: Any) -> bool:
    """Claim this user's identities. False if any of them claimed before."""
    identities = identities_of(user)
    if not identities:
        logger.warning(
            "No identity source recognised user %s; signup credit is ungated.",
            getattr(user, "id", "<unknown>"),
        )
        return True

    # Single statement: concurrent signups on one identity must not both win.
    claimed = await session.execute(
        postgres_insert(SignupCreditClaim)
        .values(
            [
                {
                    "identity_kind": identity.kind,
                    "identity_fingerprint": identity.fingerprint,
                }
                for identity in identities
            ]
        )
        .on_conflict_do_nothing(
            index_elements=["identity_kind", "identity_fingerprint"]
        )
        .returning(SignupCreditClaim.id)
    )

    return len(claimed.scalars().all()) == len(identities)
