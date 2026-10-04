"""What a live run leaves for the maintainer, written without calling a model."""

import json
from pathlib import Path

import pytest

from tests.live.run_folder import RunFolder
from tests.live.spend_ledger import SpendLedger, Usage

pytestmark = pytest.mark.unit


def test_the_cost_says_how_many_calls_were_charged_at_an_estimate(
    tmp_path: Path,
) -> None:
    """An estimated charge is a ceiling, not a bill, and the maintainer must see which is which."""
    run = RunFolder("demo-flow", root=tmp_path)
    exchanges = [{"usage_estimated": False}, {"usage_estimated": True}]

    run.finish(
        exchanges=exchanges,
        usage=Usage(input_tokens=1000),
        ledger=SpendLedger(tmp_path / "spend.json"),
        outcome="passed",
        detail="",
        redact=lambda text: text,
        word_previews={"unavailable": "LibreOffice is not installed"},
    )

    cost = json.loads((run.path / "cost.json").read_text(encoding="utf-8"))
    assert cost["model_requests"] == 2
    assert cost["estimated_model_requests"] == 1
    result = json.loads((run.path / "result.json").read_text(encoding="utf-8"))
    assert result["word_previews"] == {"unavailable": "LibreOffice is not installed"}
