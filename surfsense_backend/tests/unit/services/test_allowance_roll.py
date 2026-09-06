"""Unit tests for ``wallet_credit.roll_allowance_if_due``.

Two rules carry the risk here. A paid plan must never self-grant on a timer —
that would hand a month of usage to someone whose card just failed, since the
real grant arrives with ``invoice.paid``. And a free user's negative balance
must be written off at the roll, because a settled run can overshoot the wallet
by roughly the priciest single call ($1.95 measured) and carrying that against
a $1.00 monthly grant would cost them two months over one run they did not
cause. A buyer's debt stands.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.config import config
from app.services.wallet_credit import (
    roll_allowance_if_due,
    start_first_allowance_period,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
LAPSED = NOW - timedelta(days=1)
FUTURE = NOW + timedelta(days=1)


class _User:
    """Stands in for the User ORM row at the columns the roll touches."""

    def __init__(self, *, plan="free", allowance=0, balance=0, period_end=LAPSED):
        self.id = "user-1"
        self.plan = plan
        self.credit_micros_allowance = allowance
        self.credit_micros_balance = balance
        self.allowance_period_end = period_end


class _Session:
    """Answers the one query the roll makes, and counts whether it ran."""

    def __init__(self, has_paid: bool = False):
        self._has_paid = has_paid
        self.queries = 0

    async def execute(self, _query):
        self.queries += 1
        paid = self._has_paid

        class _Result:
            @staticmethod
            def first():
                return ("purchase-1",) if paid else None

        return _Result()


@pytest.mark.asyncio
async def test_a_lapsed_free_period_grants_the_monthly_allowance():
    user = _User(allowance=0)
    assert await roll_allowance_if_due(_Session(), user, now=NOW) is True
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_FREE
    assert user.allowance_period_end > NOW


@pytest.mark.asyncio
async def test_a_live_period_is_left_alone():
    user = _User(allowance=42, period_end=FUTURE)
    assert await roll_allowance_if_due(_Session(), user, now=NOW) is False
    assert user.credit_micros_allowance == 42, "must not top up mid-period"
    assert user.allowance_period_end == FUTURE


@pytest.mark.asyncio
async def test_an_account_never_on_a_period_starts_one():
    """The safety net for accounts predating the plan columns.

    Also covers a signup whose best-effort allowance grant did not land: the
    account gets its allowance on the first premium turn instead of silently
    having none.
    """
    user = _User(period_end=None)
    assert await roll_allowance_if_due(_Session(), user, now=NOW) is True
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_FREE
    assert user.allowance_period_end > NOW


@pytest.mark.asyncio
async def test_a_paid_account_never_on_a_period_still_does_not_self_grant():
    """A null period must not become a backdoor around the paid-plan rule.

    Reachable if a subscription webhook set the plan but the invoice that
    carries the period was never delivered.
    """
    user = _User(plan="pro", period_end=None)
    assert await roll_allowance_if_due(_Session(), user, now=NOW) is False
    assert user.credit_micros_allowance == 0
    assert user.allowance_period_end is None


@pytest.mark.asyncio
async def test_unused_allowance_does_not_roll_over():
    user = _User(allowance=999_999)
    await roll_allowance_if_due(_Session(), user, now=NOW)
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_FREE


@pytest.mark.asyncio
async def test_a_paid_plan_never_self_grants():
    """The invoice webhook grants a paid allowance, never the clock.

    If this regresses, a subscriber whose payment failed keeps getting a full
    month of usage every thirty days, forever.
    """
    user = _User(plan="pro", allowance=0)
    assert await roll_allowance_if_due(_Session(), user, now=NOW) is False
    assert user.credit_micros_allowance == 0
    assert user.allowance_period_end == LAPSED, "period must not advance either"


@pytest.mark.asyncio
async def test_overshoot_debt_is_written_off_for_someone_who_never_paid():
    user = _User(balance=-1_950_000)
    session = _Session(has_paid=False)
    await roll_allowance_if_due(session, user, now=NOW)
    assert user.credit_micros_balance == 0
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_FREE


@pytest.mark.asyncio
async def test_a_buyers_debt_survives_the_roll():
    user = _User(balance=-1_950_000)
    await roll_allowance_if_due(_Session(has_paid=True), user, now=NOW)
    assert user.credit_micros_balance == -1_950_000, "nets against their next top-up"
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_FREE


@pytest.mark.asyncio
async def test_a_positive_balance_is_never_touched():
    """Purchased credit must survive a roll regardless of who bought it."""
    for has_paid in (True, False):
        user = _User(balance=5_000_000)
        session = _Session(has_paid=has_paid)
        await roll_allowance_if_due(session, user, now=NOW)
        assert user.credit_micros_balance == 5_000_000
        assert session.queries == 0, "no purchase lookup when nothing is owed"


@pytest.mark.asyncio
async def test_the_purchase_lookup_only_runs_when_something_is_owed():
    """The roll sits on the turn's hot path; it must not add a query per turn."""
    session = _Session()
    await roll_allowance_if_due(session, _User(balance=10), now=NOW)
    assert session.queries == 0


class _CapturingSession:
    """Captures the UPDATE the signup grant issues, without a database."""

    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return None


@pytest.mark.asyncio
async def test_the_signup_grant_sets_the_allowance_and_the_period_together():
    """Both columns or neither.

    Setting only the period would leave a new account with a live period and a
    zero allowance, which reads as "already granted" — so the roll would skip
    it and the user would have nothing for thirty days.
    """
    session = _CapturingSession()
    granted = await start_first_allowance_period(session, "user-1", now=NOW)

    assert granted == config.PLAN_ALLOWANCE_MICROS_FREE
    assert len(session.statements) == 1

    params = session.statements[0].compile().params
    assert params["credit_micros_allowance"] == config.PLAN_ALLOWANCE_MICROS_FREE
    assert params["allowance_period_end"] == NOW + timedelta(days=30)


@pytest.mark.asyncio
async def test_the_signup_grant_writes_nothing_when_the_plan_grants_nothing(
    monkeypatch,
):
    """Self-hosted installs can zero the free grant; that must not write a
    period, which would then block the roll for thirty days."""
    monkeypatch.setattr(config, "PLAN_ALLOWANCE_MICROS_FREE", 0)
    session = _CapturingSession()

    assert await start_first_allowance_period(session, "user-1", now=NOW) == 0
    assert session.statements == []
