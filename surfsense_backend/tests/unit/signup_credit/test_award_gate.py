"""Signing up while no promotion is running must not spend the claim.

The signup grant is 0 now: the monthly plan allowance replaced it. The claim
ledger is what makes the grant once-per-person, and it is written *before* any
credit moves, so the order of those two steps decides whether every account
created between promotions is quietly disqualified from the next one.

Nothing else asserts this. The integration tests cover the ledger, but they
need a live database, so this is the check that runs everywhere.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import config
from app.signup_credit.award import award_signup_credit

pytestmark = pytest.mark.unit


class _RefusingSession:
    """Fails the test if the grant path touches the database at all."""

    def __init__(self) -> None:
        self.statements = 0

    async def execute(self, *_args, **_kwargs):
        self.statements += 1
        raise AssertionError(
            "award_signup_credit issued a statement with the grant switched off"
        )


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        id="6f1c8b1e-0000-4000-8000-000000000000",
        oauth_accounts=[SimpleNamespace(oauth_name="google", account_id="108231")],
    )


@pytest.mark.asyncio
async def test_a_zero_grant_claims_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DEFAULT_CREDIT_MICROS_BALANCE", 0)
    session = _RefusingSession()

    assert await award_signup_credit(session, _user()) == 0
    assert session.statements == 0, "the once-per-person claim was burned for nothing"


@pytest.mark.asyncio
async def test_a_negative_grant_is_treated_as_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A misconfigured env must not credit a negative amount, which would put
    the account below zero and read as debt it never incurred."""
    monkeypatch.setattr(config, "DEFAULT_CREDIT_MICROS_BALANCE", -1_000_000)
    session = _RefusingSession()

    assert await award_signup_credit(session, _user()) == 0
    assert session.statements == 0


@pytest.mark.asyncio
async def test_a_running_promotion_still_reaches_the_ledger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard must gate on the amount only. If it also short-circuited a real
    promotion, the grant would silently never pay out."""
    monkeypatch.setattr(config, "DEFAULT_CREDIT_MICROS_BALANCE", 5_000_000)
    session = _RefusingSession()

    with pytest.raises(AssertionError, match="grant switched off"):
        await award_signup_credit(session, _user())

    assert session.statements == 1, "a live promotion must attempt the claim"
