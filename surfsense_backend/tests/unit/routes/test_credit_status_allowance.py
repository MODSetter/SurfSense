"""The wallet fields ``GET /stripe/credit-status`` reports to the sidebar.

The sidebar renders "$2.40 of $6.00 monthly usage left", which needs both what
is left of the allowance and what the plan grants. Only the first is a column;
the second is config, and the two are easy to confuse because on a fresh period
they hold the same number. Wiring the grant to the user's remaining balance
would read "$2.40 of $2.40" forever — always plausible, never right.

The plan also has to come from config rather than the frontend, since the
amounts are environment-overridable and a hardcoded copy would drift.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.config import config
from app.routes.stripe_routes import get_credit_status

pytestmark = pytest.mark.unit

PERIOD_END = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


class _User:
    def __init__(self, *, plan="free", allowance=0, balance=0, period_end=PERIOD_END):
        self.plan = plan
        self.credit_micros_allowance = allowance
        self.credit_micros_balance = balance
        self.allowance_period_end = period_end


class _Auth:
    def __init__(self, user: _User):
        self.user = user


@pytest.mark.asyncio
async def test_the_grant_is_the_plan_total_not_what_is_left():
    """The one failure that would look right on a fresh period and wrong after
    the first spend."""
    spent_most_of_it = 2_400_000
    user = _User(plan="pro", allowance=spent_most_of_it)

    status = await get_credit_status(auth=_Auth(user))

    assert status.credit_micros_allowance == spent_most_of_it
    assert status.allowance_granted_micros == config.PLAN_ALLOWANCE_MICROS_PRO
    assert status.allowance_granted_micros > status.credit_micros_allowance


@pytest.mark.asyncio
async def test_each_plan_reports_its_own_grant():
    free = await get_credit_status(auth=_Auth(_User(plan="free")))
    pro = await get_credit_status(auth=_Auth(_User(plan="pro")))

    assert free.allowance_granted_micros == config.PLAN_ALLOWANCE_MICROS_FREE
    assert pro.allowance_granted_micros == config.PLAN_ALLOWANCE_MICROS_PRO
    assert free.plan == "free"
    assert pro.plan == "pro"


@pytest.mark.asyncio
async def test_a_null_plan_is_reported_as_free():
    """Rows written before the plan column existed carry NULL, and the tooltip
    would otherwise label them "null plan"."""
    user = _User()
    user.plan = None

    status = await get_credit_status(auth=_Auth(user))

    assert status.plan == "free"
    assert status.allowance_granted_micros == config.PLAN_ALLOWANCE_MICROS_FREE


@pytest.mark.asyncio
async def test_the_period_end_rides_along_for_the_reset_date():
    status = await get_credit_status(auth=_Auth(_User(plan="pro")))
    assert status.allowance_period_end == PERIOD_END


@pytest.mark.asyncio
async def test_a_missing_period_end_is_not_an_error():
    """Self-hosted installs and anyone predating the backfill have no period."""
    status = await get_credit_status(auth=_Auth(_User(period_end=None)))
    assert status.allowance_period_end is None
