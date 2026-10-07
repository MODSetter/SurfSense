"""How an attempt counts, read from folders trimmed from real recorded runs: retried only when it was not the model."""

import json
import shutil
from pathlib import Path

import pytest

from tests.live.sweep.attempt import classify
from tests.live.sweep.process import Process
from tests.live.sweep.retry_rule import context_overflow, transient

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).parent / "fixtures"
DONE = Process(exit_code=1, seconds=120.0, peak_mb=900, lane=0)


def _fixture(name: str, tmp_path: Path) -> Path:
    copied = tmp_path / name
    shutil.copytree(FIXTURES / name, copied)
    return copied


def _classify(folder: Path, root: Path, process: Process = DONE, capped: bool = True):
    return classify(folder, process, root, capped_by_case=capped)


def test_a_turn_the_provider_ended_is_transient(tmp_path: Path) -> None:
    """The last request dropped its connection and the turn never completed."""
    ending = _classify(_fixture("provider_ended_the_turn", tmp_path), tmp_path)

    assert ending.outcome == "transient"
    assert ending.reason.startswith("RemoteProtocolError")
    assert ending.served_by == ["InferenceNet", "Morph"]


def test_a_blip_opencode_recovered_from_does_not_buy_a_second_roll(
    tmp_path: Path,
) -> None:
    """Qwen3.8 dropped two connections mid-run, recovered, then made no PDF: that failure is its own."""
    ending = _classify(
        _fixture("recovered_blip_then_content_failure", tmp_path), tmp_path
    )

    assert ending.outcome == "failed"
    assert "no PDF was made" in ending.reason


def test_a_context_length_refusal_is_the_models(tmp_path: Path) -> None:
    """Qwen3.6's 400 'Provider returned error' was its window overflowing."""
    ending = _classify(_fixture("context_overflow", tmp_path), tmp_path)

    assert (ending.outcome, ending.kind) == ("failed", "context-overflow")


def test_an_assertion_failure_is_the_models_and_costs_what_openrouter_billed(
    tmp_path: Path,
) -> None:
    """Gemma's unopened preview; the reported $0.0111 is preferred to the ledger's $0.0024."""
    ending = _classify(_fixture("assertion_failure", tmp_path), tmp_path)

    assert ending.outcome == "failed"
    assert "never opened page" in ending.reason
    assert (ending.cost, ending.reported) == (0.0111, True)
    assert ending.run_folder == "assertion_failure/20261005T000000Z-run"


def test_without_a_reported_bill_the_cost_is_the_ledgers(tmp_path: Path) -> None:
    """A run with a cut-off request has no bill from OpenRouter; its ledger's dollars stand in."""
    ending = _classify(_fixture("provider_ended_the_turn", tmp_path), tmp_path)

    assert (ending.cost, ending.reported) == (0.7612, False)


def test_a_thread_the_app_opened_as_a_chat_is_a_harness_fault(tmp_path: Path) -> None:
    """opencode never served, so the app answered MiMo as a chat with no tools."""
    ending = _classify(_fixture("thread_opened_as_a_chat", tmp_path), tmp_path)

    assert ending.outcome == "harness"
    assert "opened as a chat" in ending.reason


def test_harness_faults_are_ours(tmp_path: Path) -> None:
    """No result.json, a crash, an app error, or a fault before the first model request."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert _classify(empty, tmp_path).reason == "no result.json"

    folder = _fixture("assertion_failure", tmp_path)
    assert _classify(folder, tmp_path, Process(exit_code=3, seconds=5.0)).outcome == (
        "harness"
    )
    (run,) = folder.iterdir()
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    result["detail"] = (
        "E   httpx.HTTPStatusError: Server error '500 Internal Server Error'"
    )
    (run / "result.json").write_text(json.dumps(result), encoding="utf-8")
    assert _classify(folder, tmp_path).reason.startswith("app error")

    (run / "model-requests.json").write_text("[]", encoding="utf-8")
    result["detail"] = "E   AssertionError: no version"
    (run / "result.json").write_text(json.dumps(result), encoding="utf-8")
    assert _classify(folder, tmp_path).reason == "failed before the first model request"


def test_a_print_that_timed_out_is_a_harness_fault(tmp_path: Path) -> None:
    """A slow machine must not cost a model its previews."""
    folder = _fixture("assertion_failure", tmp_path)
    (run,) = folder.iterdir()
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    result["word_previews"] = {"failures": ["TimeoutExpired: soffice took 25 s"]}
    (run / "result.json").write_text(json.dumps(result), encoding="utf-8")

    assert _classify(folder, tmp_path).outcome == "harness"


def test_a_run_killed_at_the_time_limit_is_the_models_only_if_it_wrote_anything(
    tmp_path: Path,
) -> None:
    """A runaway model spent output tokens; a provider that sent nothing is transient."""
    killed = Process(exit_code=1, seconds=1200.0, timed_out=True)
    runaway = tmp_path / "runaway"
    runaway.mkdir()
    (runaway / "spend.json").write_text(
        json.dumps({"dollars": 0.4, "by_model": {"m": {"output_tokens": 9000}}}),
        encoding="utf-8",
    )
    silent = tmp_path / "silent"
    silent.mkdir()

    ran = _classify(runaway, tmp_path, killed)
    assert (ran.outcome, ran.kind, ran.cost) == ("failed", "timeout", 0.4)
    assert _classify(silent, tmp_path, killed).outcome == "transient"


def test_a_budget_stop_is_the_models_at_the_case_cap_and_the_sweeps_otherwise(
    tmp_path: Path,
) -> None:
    """Spending past the per-case cap is a runaway; reaching the sweep's last dollars is not the model's doing."""
    folder = _fixture("assertion_failure", tmp_path)
    (folder / "pytest.log").write_text(
        "error: live budget stop: $3.01 spent of the $3 stop", encoding="utf-8"
    )

    capped = _classify(folder, tmp_path, capped=True)
    assert (capped.outcome, capped.kind) == ("failed", "case-cap")
    assert _classify(folder, tmp_path, capped=False).outcome == "budget"


def test_what_counts_as_transient() -> None:
    """Rate limits, server errors, dropped connections and OpenRouter's wrapped upstream errors; not other 400s."""
    assert transient({"status": 429})
    assert transient({"status": 503})
    assert transient({"status": 0, "error": "ReadError: [SSL] bad record mac"})
    assert transient({"status": 200, "error": '{"code": 529, "message": "Overloaded"}'})
    assert transient(
        {
            "status": 400,
            "error": '{"error":{"message":"Provider returned error","code":400}}',
        }
    )
    assert not transient(
        {"status": 400, "error": '{"error":{"message":"invalid tool schema"}}'}
    )
    overflow = {
        "status": 400,
        "error": '{"error":{"message":"Provider returned error","metadata":'
        '{"raw":"exceeds the model\'s maximum context length"}}}',
    }
    assert context_overflow(overflow) and not transient(overflow)
