"""The signup credit is earned by a person, not by an account row."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.db import User
from app.signup_credit.award import award_signup_credit

pytestmark = pytest.mark.integration


async def signup(session: AsyncSession, google_sub: str) -> User:
    """A brand-new account authenticated by ``google_sub``."""
    user = User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex[:8]}@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    # oauth_accounts is mapped only under AUTH_TYPE=GOOGLE; the suite runs LOCAL.
    user.oauth_accounts = [SimpleNamespace(oauth_name="google", account_id=google_sub)]
    session.add(user)
    await session.flush()
    return user


async def balance_of(session: AsyncSession, user: User) -> int:
    await session.refresh(user)
    return user.credit_micros_balance


async def test_a_first_time_identity_is_credited(db_session: AsyncSession):
    newcomer = await signup(db_session, "sub-newcomer")

    await award_signup_credit(db_session, newcomer)

    assert (
        await balance_of(db_session, newcomer) == config.DEFAULT_CREDIT_MICROS_BALANCE
    )


async def test_re_registering_on_a_spent_identity_is_credited_nothing(
    db_session: AsyncSession,
):
    """Delete-and-re-register is the credit farm this ledger exists to close."""
    first_account = await signup(db_session, "sub-returning")
    await award_signup_credit(db_session, first_account)

    second_account = await signup(db_session, "sub-returning")
    await award_signup_credit(db_session, second_account)

    assert await balance_of(db_session, second_account) == 0
