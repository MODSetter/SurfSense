"""What a live run leaves for the maintainer, written without calling a model."""

import json
from pathlib import Path

import pytest

from tests.live.live_model import PROVIDERS, LiveModel
from tests.live.model_prices import Prices
from tests.live.run_folder import RunFolder
from tests.live.spend_ledger import SpendLedger, Usage

pytestmark = pytest.mark.unit

HAIKU = LiveModel(
    "anthropic/claude-haiku-4.5",
    PROVIDERS["openrouter"],
    Prices(input=1.0, output=5.0, cache_read=0.1, cache_write=1.25),
)


def _finish(run: RunFolder, tmp_path: Path, exchanges: list[dict]) -> None:
    run.finish(
        exchanges=exchanges,
        usage=Usage(input_tokens=1000, output_tokens=100),
        ledger=SpendLedger(tmp_path / "spend.json"),
        outcome="passed",
        detail="",
        redact=lambda text: text,
        word_previews={"unavailable": "LibreOffice is not installed"},
    )


def test_the_cost_says_how_many_calls_were_charged_at_an_estimate(
    tmp_path: Path,
) -> None:
    """An estimated charge is a ceiling, not a bill, and the maintainer must see which is which."""
    run = RunFolder("demo-flow", HAIKU, root=tmp_path)

    _finish(run, tmp_path, [{"usage_estimated": False}, {"usage_estimated": True}])

    cost = json.loads((run.path / "cost.json").read_text(encoding="utf-8"))
    assert cost["model_requests"] == 2
    assert cost["estimated_model_requests"] == 1
    result = json.loads((run.path / "result.json").read_text(encoding="utf-8"))
    assert result["word_previews"] == {"unavailable": "LibreOffice is not installed"}


def test_the_run_says_which_model_and_provider_it_ran_on_and_at_what_prices(
    tmp_path: Path,
) -> None:
    """A ladder compares models; a run that does not name its own is unreadable."""
    run = RunFolder("smoke", HAIKU, root=tmp_path)

    _finish(run, tmp_path, [])

    assert run.path.name.endswith("-smoke-openrouter-anthropic_claude-haiku-4.5")
    cost = json.loads((run.path / "cost.json").read_text(encoding="utf-8"))
    assert cost["model"] == "anthropic/claude-haiku-4.5"
    assert cost["provider"] == "openrouter"
    assert cost["dollars"] == pytest.approx((1000 * 1.0 + 100 * 5.0) / 1e6)
    assert cost["prices_per_million"]["output_tokens"] == 5.0
    result = json.loads((run.path / "result.json").read_text(encoding="utf-8"))
    assert result["model"] == "anthropic/claude-haiku-4.5"
    assert result["provider"] == "openrouter"
    assert result["reads_images"] is True


def test_runs_go_where_the_sweep_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SURFSENSE_LIVE_RUNS_DIR, beside the sweep's own ledger."""
    monkeypatch.setenv("SURFSENSE_LIVE_RUNS_DIR", str(tmp_path / "ladder"))

    run = RunFolder("smoke", HAIKU)

    assert run.path.parent == tmp_path / "ladder"


def test_the_cost_carries_what_openrouter_billed_when_every_call_says(
    tmp_path: Path,
) -> None:
    """OpenRouter bills each call at the provider it routed to, not the listed price."""
    billed = RunFolder("smoke", HAIKU, root=tmp_path / "billed")
    _finish(
        billed,
        tmp_path,
        [
            {"usage_estimated": False, "reported_cost": 0.0102},
            {"usage_estimated": False, "reported_cost": 0.0051},
        ],
    )
    unbilled = RunFolder("smoke", HAIKU, root=tmp_path / "unbilled")
    _finish(
        unbilled,
        tmp_path,
        [
            {"usage_estimated": False, "reported_cost": 0.0102},
            {"usage_estimated": True},
        ],
    )

    cost = json.loads((billed.path / "cost.json").read_text(encoding="utf-8"))
    assert cost["reported_dollars"] == pytest.approx(0.0153)
    cost = json.loads((unbilled.path / "cost.json").read_text(encoding="utf-8"))
    assert cost["reported_dollars"] is None
