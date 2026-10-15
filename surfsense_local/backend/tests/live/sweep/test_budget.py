"""The sweep's cap: a case starts only if it fits beside what is spent and in flight, and each run gets its own stop."""

import pytest

from tests.live.sweep.budget import Budget, estimate
from tests.live.sweep.model_list import ListedModel

pytestmark = pytest.mark.unit

SONNET_PRICED = ListedModel("a/b", "b", 2.0, 10.0, 200_000, True)


def test_a_case_is_expected_to_cost_its_tokens_at_the_listed_prices() -> None:
    """About twice what Sonnet's passing runs cost on the ladder ($0.34 and $0.48)."""
    assert estimate(SONNET_PRICED, "pdf-brief") == pytest.approx(0.62)
    assert estimate(SONNET_PRICED, "board-pack") == pytest.approx(0.72)
    assert estimate(SONNET_PRICED, "smoke") == pytest.approx(0.1)


def test_a_case_starts_only_while_spent_plus_in_flight_plus_its_own_fits() -> None:
    """The cap holds what is spent, what is in flight and the new case together."""
    budget = Budget(cap=10.0, case_cap=3.0)

    assert budget.may_start(spent=8.0, in_flight=[1.0], expected=1.0)
    assert not budget.may_start(spent=8.0, in_flight=[1.0], expected=1.01)


def test_a_runs_stop_is_the_case_cap_or_the_sweeps_last_dollars() -> None:
    """A run may spend the per-case cap, or less when that is all the sweep has left."""
    budget = Budget(cap=10.0, case_cap=3.0)

    assert budget.stop_for(spent=2.0, in_flight=[1.0]) == (3.0, True)
    assert budget.stop_for(spent=7.0, in_flight=[1.5]) == (1.5, False)
    assert budget.stop_for(spent=11.0, in_flight=[]) == (0.0, False)
