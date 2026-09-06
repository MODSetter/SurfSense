"""Unit tests for the Stripe subscription webhook handlers.

Three rules carry the money risk.

An ``invoice.paid`` retry must not re-grant. Stripe retries a failed delivery
for up to three days, so a handler that adds or overwrites unconditionally would
refill an allowance the user has already spent. The guard is that the paid period
must end later than the one on record.

A subscription going ``active`` must not grant anything. Only ``invoice.paid``
proves the card charged, so granting on status alone would hand a month of usage
to anyone who reached checkout with a card that then declined.

A one-time credit top-up must never look like a plan. It shares the webhook and
the wallet, and mistaking it for a subscription would grant a free allowance with
every $1 purchase.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import config
from app.routes.stripe_routes import _apply_paid_invoice, _apply_subscription_state

pytestmark = pytest.mark.unit

PRO_PRICE = "price_test_pro_monthly"
CREDIT_PRICE = "price_test_credit_pack"

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
PERIOD_1 = NOW + timedelta(days=30)
PERIOD_2 = NOW + timedelta(days=60)


@pytest.fixture(autouse=True)
def _pro_price(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_PRO_PRICE_ID", PRO_PRICE)


class _Obj:
    """Stands in for a StripeObject: attribute access over a plain dict."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _User:
    def __init__(self, *, plan="free", allowance=0, period_end=None, balance=0):
        self.id = "11111111-2222-3333-4444-555555555555"
        self.plan = plan
        self.credit_micros_allowance = allowance
        self.allowance_period_end = period_end
        self.credit_micros_balance = balance
        self.stripe_customer_id = "cus_test"


class _Session:
    """Returns the one user the handlers look up, and counts commits."""

    def __init__(self, user: _User | None):
        self._user = user
        self.commits = 0

    async def execute(self, _query):
        user = self._user

        class _Result:
            @staticmethod
            def unique():
                return _Result()

            @staticmethod
            def scalar_one_or_none():
                return user

        return _Result()

    async def commit(self):
        self.commits += 1


def _invoice(price_id: str, period_end: datetime | None, *, user_id=None):
    line = _Obj(
        pricing=_Obj(price_details=_Obj(price=price_id)),
        period=_Obj(end=int(period_end.timestamp())) if period_end else _Obj(end=None),
    )
    return _Obj(
        id="in_test",
        customer="cus_test",
        lines=_Obj(data=[line]),
        parent=_Obj(
            subscription_details=_Obj(
                subscription="sub_test",
                metadata={"user_id": user_id} if user_id else {},
            )
        ),
    )


def _subscription(price_id: str, status: str, period_end: datetime = PERIOD_1):
    return _Obj(
        id="sub_test",
        customer="cus_test",
        status=status,
        metadata={},
        items=_Obj(
            data=[
                _Obj(
                    price=_Obj(id=price_id),
                    current_period_end=int(period_end.timestamp()),
                )
            ]
        ),
    )


@pytest.mark.asyncio
async def test_a_paid_invoice_grants_the_plan_allowance():
    user = _User()
    session = _Session(user)
    await _apply_paid_invoice(session, _invoice(PRO_PRICE, PERIOD_1))

    assert user.plan == "pro"
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_PRO
    assert user.allowance_period_end == PERIOD_1
    assert session.commits == 1


@pytest.mark.asyncio
async def test_a_retried_invoice_does_not_refill_a_spent_allowance():
    """The whole reason no ledger table is needed. If this breaks, a Stripe
    retry three days later hands the user a second month for free."""
    user = _User()
    invoice = _invoice(PRO_PRICE, PERIOD_1)
    await _apply_paid_invoice(_Session(user), invoice)

    user.credit_micros_allowance = 12_345  # they have been spending
    session = _Session(user)
    await _apply_paid_invoice(session, invoice)

    assert user.credit_micros_allowance == 12_345
    assert session.commits == 0, "must not even write"


@pytest.mark.asyncio
async def test_a_renewal_does_grant_again():
    user = _User(plan="pro", allowance=0, period_end=PERIOD_1)
    await _apply_paid_invoice(_Session(user), _invoice(PRO_PRICE, PERIOD_2))

    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_PRO
    assert user.allowance_period_end == PERIOD_2


@pytest.mark.asyncio
async def test_upgrading_grants_even_when_the_free_period_ends_later():
    """The free roll and Stripe's billing month are different clocks.

    A free user's lazy roll sets the period 30 days out. Stripe's first Pro
    period is one *calendar* month, which in February is only 28 days. Comparing
    the two as if they were the same clock rejects the first paid grant, so the
    customer is charged $15 and receives nothing.
    """
    free_roll_end = NOW + timedelta(days=30)
    stripe_first_period_end = NOW + timedelta(days=28)
    user = _User(
        plan="free",
        allowance=config.PLAN_ALLOWANCE_MICROS_FREE,
        period_end=free_roll_end,
    )

    session = _Session(user)
    await _apply_paid_invoice(
        session, _invoice(PRO_PRICE, stripe_first_period_end), now=NOW
    )

    assert user.plan == "pro"
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_PRO
    assert user.allowance_period_end == stripe_first_period_end


@pytest.mark.asyncio
async def test_an_invoice_for_an_already_elapsed_period_is_refused():
    """A retry that lands after the period it paid for must not grant.

    Granting it would set ``plan="pro"`` with a period end in the past, and
    ``roll_allowance_if_due`` refuses to roll a paid plan — so the allowance
    would never expire.
    """
    user = _User()
    session = _Session(user)
    await _apply_paid_invoice(
        session, _invoice(PRO_PRICE, NOW - timedelta(days=1)), now=NOW
    )

    assert user.credit_micros_allowance == 0
    assert user.plan == "free"
    assert session.commits == 0


@pytest.mark.asyncio
async def test_a_credit_top_up_invoice_grants_no_allowance():
    user = _User()
    session = _Session(user)
    await _apply_paid_invoice(session, _invoice(CREDIT_PRICE, PERIOD_1))

    assert user.plan == "free"
    assert user.credit_micros_allowance == 0
    assert user.allowance_period_end is None
    assert session.commits == 0


@pytest.mark.asyncio
async def test_an_unknown_user_is_logged_not_granted():
    session = _Session(None)
    await _apply_paid_invoice(session, _invoice(PRO_PRICE, PERIOD_1))
    assert session.commits == 0


@pytest.mark.asyncio
async def test_going_active_sets_the_plan_but_grants_nothing():
    user = _User()
    await _apply_subscription_state(_Session(user), _subscription(PRO_PRICE, "active"))

    assert user.plan == "pro"
    assert user.credit_micros_allowance == 0, "the grant belongs to invoice.paid"
    assert user.allowance_period_end is None


@pytest.mark.asyncio
async def test_cancellation_downgrades_and_clamps_the_allowance():
    user = _User(plan="pro", allowance=config.PLAN_ALLOWANCE_MICROS_PRO)
    await _apply_subscription_state(
        _Session(user), _subscription(PRO_PRICE, "canceled"), deleted=True
    )

    assert user.plan == "free"
    assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_FREE


@pytest.mark.asyncio
async def test_a_downgrade_never_raises_a_smaller_leftover():
    """Clamping is a floor on nothing: someone mid-period with less left than a
    free month keeps only what they had."""
    user = _User(plan="pro", allowance=1_000)
    await _apply_subscription_state(
        _Session(user), _subscription(PRO_PRICE, "canceled"), deleted=True
    )
    assert user.credit_micros_allowance == 1_000


@pytest.mark.asyncio
async def test_dunning_does_not_pull_access():
    """past_due means Stripe is still retrying the card. Downgrading here
    punishes someone who is about to pay."""
    for still_trying in ("past_due", "incomplete"):
        user = _User(plan="pro", allowance=config.PLAN_ALLOWANCE_MICROS_PRO)
        session = _Session(user)
        await _apply_subscription_state(session, _subscription(PRO_PRICE, still_trying))
        assert user.plan == "pro", still_trying
        assert user.credit_micros_allowance == config.PLAN_ALLOWANCE_MICROS_PRO
        assert session.commits == 0


@pytest.mark.asyncio
async def test_unpaid_after_dunning_does_downgrade():
    user = _User(plan="pro", allowance=config.PLAN_ALLOWANCE_MICROS_PRO)
    await _apply_subscription_state(_Session(user), _subscription(PRO_PRICE, "unpaid"))
    assert user.plan == "free"


@pytest.mark.asyncio
async def test_a_subscription_on_an_unknown_price_is_ignored():
    """Guards against a second product downgrading Pro users by accident."""
    user = _User(plan="pro", allowance=config.PLAN_ALLOWANCE_MICROS_PRO)
    session = _Session(user)
    await _apply_subscription_state(
        session, _subscription("price_some_other_product", "canceled"), deleted=True
    )
    assert user.plan == "pro"
    assert session.commits == 0


@pytest.mark.asyncio
async def test_metadata_user_id_is_preferred_over_the_customer_id():
    user = _User()
    session = _Session(user)
    await _apply_paid_invoice(session, _invoice(PRO_PRICE, PERIOD_1, user_id=user.id))
    assert user.plan == "pro"


@pytest.mark.asyncio
async def test_an_invoice_with_no_period_is_ignored():
    """A missing period would otherwise be granted with a NULL end, which the
    lazy roll reads as 'never on a plan' and would leave stuck."""
    user = _User()
    session = _Session(user)
    await _apply_paid_invoice(session, _invoice(PRO_PRICE, None))
    assert user.credit_micros_allowance == 0
    assert session.commits == 0


def test_the_credit_price_never_resolves_to_a_plan(monkeypatch):
    monkeypatch.setattr(config, "STRIPE_CREDIT_PRICE_ID", CREDIT_PRICE)
    assert config.plan_for_price_id(CREDIT_PRICE) is None
    assert config.plan_for_price_id(None) is None
    assert config.plan_for_price_id(PRO_PRICE) == "pro"


def test_no_price_configured_means_no_plan_can_be_granted(monkeypatch):
    """Self-hosted installs leave STRIPE_PRO_PRICE_ID unset. A None price id
    must not match a None config value and silently upgrade everyone."""
    monkeypatch.setattr(config, "STRIPE_PRO_PRICE_ID", None)
    assert config.plan_for_price_id(None) is None
    assert config.plan_for_price_id("") is None
