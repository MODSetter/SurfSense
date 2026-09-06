"""Unit tests for the two-bucket wallet split (``wallet_credit.drain``).

The wallet holds a resetting plan allowance and a permanent balance. Every
debit path — premium model calls, ETL pages, crawl, platform scrape — routes
through ``drain`` so the order between the buckets is decided in one place.

The load-bearing case is the last one: with a zero allowance, ``drain`` must be
byte-for-byte equivalent to the ``balance -= cost`` it replaced. That is what
makes shipping the columns ahead of any grant a no-op deploy.
"""

import pytest

from app.services.wallet_credit import drain, funds_micros

pytestmark = pytest.mark.unit


class _Wallet:
    """Stands in for the User ORM row at the two columns drain touches."""

    def __init__(self, allowance: int, balance: int):
        self.credit_micros_allowance = allowance
        self.credit_micros_balance = balance

    def __repr__(self) -> str:  # pragma: no cover - assertion output only
        return (
            f"_Wallet(allowance={self.credit_micros_allowance}, "
            f"balance={self.credit_micros_balance})"
        )


def test_funds_sums_both_buckets():
    assert funds_micros(_Wallet(allowance=300, balance=700)) == 1000


def test_funds_ignores_a_negative_allowance():
    """A negative allowance must not eat into reported funds."""
    assert funds_micros(_Wallet(allowance=-500, balance=700)) == 700


def test_allowance_is_spent_before_balance():
    w = _Wallet(allowance=1000, balance=5000)
    drain(w, 400)
    assert w.credit_micros_allowance == 600
    assert w.credit_micros_balance == 5000, "purchased credit must stay untouched"


def test_exhausting_the_allowance_exactly_leaves_the_balance_alone():
    w = _Wallet(allowance=1000, balance=5000)
    drain(w, 1000)
    assert w.credit_micros_allowance == 0
    assert w.credit_micros_balance == 5000


def test_shortfall_spills_from_allowance_onto_balance():
    w = _Wallet(allowance=1000, balance=5000)
    drain(w, 1500)
    assert w.credit_micros_allowance == 0
    assert w.credit_micros_balance == 4500
    assert funds_micros(w) == 4500


def test_balance_may_go_negative_on_overage():
    """A settled provider cost can exceed its pre-charge estimate on a request
    that already ran. The debit still lands; the UI clamps the display at $0."""
    w = _Wallet(allowance=100, balance=200)
    drain(w, 1000)
    assert w.credit_micros_allowance == 0
    assert w.credit_micros_balance == -700


@pytest.mark.parametrize("cost", [0, -1, -5000])
def test_non_positive_cost_is_a_noop(cost):
    w = _Wallet(allowance=1000, balance=5000)
    drain(w, cost)
    assert (w.credit_micros_allowance, w.credit_micros_balance) == (1000, 5000)


def test_a_negative_allowance_cannot_inflate_the_charge():
    """Guard against a corrupt row billing the balance more than the cost."""
    w = _Wallet(allowance=-1000, balance=5000)
    drain(w, 300)
    assert w.credit_micros_allowance == -1000, "left as-is, not credited"
    assert w.credit_micros_balance == 4700, "charged the cost, not cost + 1000"


@pytest.mark.parametrize("cost", [1, 750, 5000, 12_345])
def test_zero_allowance_is_identical_to_the_old_balance_debit(cost):
    """Parity check: this is why the schema can ship before any grant does."""
    starting_balance = 5000
    w = _Wallet(allowance=0, balance=starting_balance)
    drain(w, cost)
    assert w.credit_micros_allowance == 0
    assert w.credit_micros_balance == starting_balance - cost


def test_repeated_drains_never_lose_or_mint_credit():
    """Total funds fall by exactly what was charged, across bucket boundaries."""
    w = _Wallet(allowance=1000, balance=2000)
    before = funds_micros(w)
    charged = 0
    for cost in (300, 300, 300, 300, 300):
        drain(w, cost)
        charged += cost
    assert funds_micros(w) == before - charged
    assert w.credit_micros_allowance == 0
    assert w.credit_micros_balance == 1500
