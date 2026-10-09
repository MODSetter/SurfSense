"""The spend ledger every live run checks before it calls a paid model."""

import json
import os
import threading
from pathlib import Path

import pytest

from tests.live.model_prices import Prices
from tests.live.spend_ledger import SpendLedger, Usage

pytestmark = pytest.mark.unit

SONNET = Prices(input=2.0, output=10.0, cache_read=0.2, cache_write=2.5)
HAIKU = Prices(input=1.0, output=5.0, cache_read=0.1, cache_write=1.25)


def test_spend_adds_up_in_dollars_across_runs_and_models(tmp_path: Path) -> None:
    """The budget covers every run on every model; tokens of two models do not add."""
    path = tmp_path / "spend.json"
    SpendLedger(path).add(
        Usage(input_tokens=500_000),
        SONNET,
        case="smoke",
        model="anthropic/claude-sonnet-5-5",
    )

    reopened = SpendLedger(path)
    reopened.add(
        Usage(output_tokens=100_000),
        HAIKU,
        case="smoke",
        model="anthropic/claude-haiku-4-5",
    )

    assert SpendLedger(path).dollars() == pytest.approx(1.50)
    stored = json.loads(path.read_text(encoding="utf-8"))
    haiku = stored["by_model"]["anthropic/claude-haiku-4-5"]
    assert haiku["output_tokens"] == 100_000
    assert haiku["dollars"] == pytest.approx(0.50)
    assert haiku["by_case"]["smoke"]["dollars"] == pytest.approx(0.50)
    assert haiku["prices_per_million"]["output_tokens"] == 5.0


def test_a_call_that_could_reach_the_stop_is_refused(tmp_path: Path) -> None:
    """The stop is a ceiling: a call is refused if its worst case would reach it."""
    ledger = SpendLedger(tmp_path / "spend.json", stop_dollars=10.0)
    ledger.add(Usage(input_tokens=4_000_000), SONNET, case="earlier", model="m")

    assert ledger.has_room(1.99) is True
    assert ledger.has_room(2.00) is False


def test_the_stop_is_45_dollars_unless_the_run_sets_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ladder sweep sets its own; the first night's $45 stays the default."""
    monkeypatch.delenv("SURFSENSE_LIVE_STOP_DOLLARS", raising=False)
    assert SpendLedger(tmp_path / "spend.json").stop_dollars == 45.0

    monkeypatch.setenv("SURFSENSE_LIVE_STOP_DOLLARS", "400")
    assert SpendLedger(tmp_path / "spend.json").stop_dollars == 400.0


def test_the_ledger_lives_in_the_runs_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sweep that moves its runs keeps its own budget."""
    monkeypatch.setenv("SURFSENSE_LIVE_RUNS_DIR", str(tmp_path / "ladder"))

    assert SpendLedger().path == tmp_path / "ladder" / "spend.json"


SONNET_ONLY = {
    "model": "claude-sonnet-5-5",
    "prices_per_million": {
        "input_tokens": 2.0,
        "output_tokens": 10.0,
        "cache_read_tokens": 0.2,
        "cache_write_tokens": 2.5,
    },
    "stop_dollars": 45.0,
    "input_tokens": 1_000_000,
    "output_tokens": 100_000,
    "cache_read_tokens": 0,
    "cache_write_tokens": 400_000,
    "dollars": 4.0,
    "updated": "2026-10-04T18:21:50+00:00",
    "by_case": {
        "smoke": {
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "cache_read_tokens": 0,
            "cache_write_tokens": 400_000,
        }
    },
}


def test_the_sonnet_only_ledger_keeps_its_total_and_is_converted_on_the_next_charge(
    tmp_path: Path,
) -> None:
    """The first night's runs were all Sonnet's, priced in the file itself."""
    path = tmp_path / "spend.json"
    path.write_text(json.dumps(SONNET_ONLY), encoding="utf-8")
    ledger = SpendLedger(path)

    assert ledger.dollars() == pytest.approx(4.0)
    ledger.add(
        Usage(output_tokens=10_000),
        HAIKU,
        case="smoke",
        model="anthropic/claude-haiku-4-5",
    )

    assert SpendLedger(path).dollars() == pytest.approx(4.05)
    stored = json.loads(path.read_text(encoding="utf-8"))
    sonnet = stored["by_model"]["anthropic/claude-sonnet-5-5"]
    assert sonnet["dollars"] == pytest.approx(4.0)
    assert sonnet["input_tokens"] == 1_000_000
    assert sonnet["prices_per_million"] == SONNET_ONLY["prices_per_million"]
    assert sonnet["by_case"]["smoke"]["dollars"] == pytest.approx(4.0)
    assert "input_tokens" not in stored


def test_an_empty_ledger_has_spent_nothing(tmp_path: Path) -> None:
    """The first run starts from no file."""
    assert SpendLedger(tmp_path / "missing" / "spend.json").dollars() == 0


@pytest.mark.skipif(
    os.name != "nt", reason="only Windows refuses to replace an open file"
)
def test_a_charge_lands_while_another_process_reads_the_ledger(tmp_path: Path) -> None:
    """The sweep's runner reads each run's ledger as the run charges it; the charge must not be lost."""
    path = tmp_path / "spend.json"
    ledger = SpendLedger(path)
    ledger.add(Usage(input_tokens=500_000), SONNET, case="smoke", model="m")
    reader = path.open("rb")
    threading.Timer(0.1, reader.close).start()

    ledger.add(Usage(input_tokens=500_000), SONNET, case="smoke", model="m")

    assert SpendLedger(path).dollars() == pytest.approx(2.0)
    assert not list(tmp_path.glob(".*.partial"))
