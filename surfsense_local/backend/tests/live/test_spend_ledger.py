"""The spend ledger every live run checks before it calls a paid model."""

from pathlib import Path

import pytest

from tests.live.spend_ledger import SpendLedger, Usage

pytestmark = pytest.mark.unit


def test_usage_is_priced_at_sonnets_rates_per_million_tokens() -> None:
    """$2 in, $10 out, $0.20 cache read, $2.50 cache write."""
    usage = Usage(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_tokens=1_000_000,
        cache_write_tokens=400_000,
    )

    assert usage.dollars == pytest.approx(2.00 + 1.00 + 0.20 + 1.00)


def test_spend_adds_up_across_runs_and_survives_a_restart(tmp_path: Path) -> None:
    """The budget covers every run, not one."""
    path = tmp_path / "spend.json"
    SpendLedger(path).add(Usage(input_tokens=500_000), case="smoke")

    reopened = SpendLedger(path)
    reopened.add(Usage(output_tokens=100_000), case="demo-flow")

    assert reopened.total() == Usage(input_tokens=500_000, output_tokens=100_000)
    assert SpendLedger(path).total().dollars == pytest.approx(2.00)


def test_a_call_that_could_reach_the_stop_is_refused(tmp_path: Path) -> None:
    """The stop is a ceiling: a call is refused if its worst case would reach it."""
    ledger = SpendLedger(tmp_path / "spend.json", stop_dollars=10.0)
    ledger.add(Usage(input_tokens=4_000_000), case="earlier")  # $8

    assert ledger.has_room(1.99) is True
    assert ledger.has_room(2.00) is False


def test_an_empty_ledger_has_spent_nothing(tmp_path: Path) -> None:
    """The first run starts from no file."""
    assert SpendLedger(tmp_path / "missing" / "spend.json").total() == Usage()
