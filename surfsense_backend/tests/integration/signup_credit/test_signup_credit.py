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


PROMO_MICROS = 5_000_000


@pytest.fixture
def promo_running(monkeypatch: pytest.MonkeyPatch) -> int:
    """A signup promotion that is actually paying out.

    The shipped grant is 0, which would make every assertion below read
    ``0 == 0`` and quietly stop covering the once-per-person ledger. Pinning an
    amount keeps these about the claim mechanism rather than the current
    default, so the protection is still tested if a promotion is ever re-run.
    """
    monkeypatch.setattr(config, "DEFAULT_CREDIT_MICROS_BALANCE", PROMO_MICROS)
    return PROMO_MICROS


async def test_a_first_time_identity_is_credited(
    db_session: AsyncSession, promo_running: int
):
    newcomer = await signup(db_session, "sub-newcomer")

    await award_signup_credit(db_session, newcomer)

    assert await balance_of(db_session, newcomer) == promo_running


async def test_re_registering_on_a_spent_identity_is_credited_nothing(
    db_session: AsyncSession, promo_running: int
):
    """Delete-and-re-register is the credit farm this ledger exists to close."""
    first_account = await signup(db_session, "sub-returning")
    await award_signup_credit(db_session, first_account)

    second_account = await signup(db_session, "sub-returning")
    await award_signup_credit(db_session, second_account)

    assert await balance_of(db_session, second_account) == 0


async def test_no_promotion_leaves_the_identity_unclaimed(db_session: AsyncSession):
    """With the grant off, signing up must not spend the once-per-person claim.

    Otherwise every account created between now and the next promotion would be
    silently ineligible for it, having burned its claim on a grant of zero.
    """
    early_bird = await signup(db_session, "sub-early-bird")

    assert await award_signup_credit(db_session, early_bird) == 0
    assert await balance_of(db_session, early_bird) == 0

    with pytest.MonkeyPatch.context() as promotion:
        promotion.setattr(config, "DEFAULT_CREDIT_MICROS_BALANCE", PROMO_MICROS)
        assert await award_signup_credit(db_session, early_bird) == PROMO_MICROS
