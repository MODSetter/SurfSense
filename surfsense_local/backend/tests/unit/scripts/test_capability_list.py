"""The capability list is written from ladder results by one rule, and the shipped one is that rule's output."""

import json
from typing import Any

import pytest
from capability_list.ladder_input import LadderResults
from capability_list.rows import COMMITTED_INPUT, measured_rows, with_ladder_rows
from capability_list.verdict import verdict

from modules.llm.capability import Level
from modules.llm.capability.measured.loader import SHIPPED
from modules.llm.capability.measured.schema import CapabilityList

pytestmark = pytest.mark.unit

SUITE_CASES = {
    "smoke": False,
    "images-reach-the-model": True,
    "demo-flow": False,
    "pdf-brief": False,
    "spreadsheet-report": False,
    "memo-restructure": False,
    "figure-swap": True,
    "board-pack": False,
}
REQUIRED = ("smoke", "demo-flow")


def _results(cases: dict[str, str], *, reads_images: bool = True) -> LadderResults:
    return LadderResults.model_validate(
        {
            "suite": "create-and-edit",
            "suite_version": 1,
            "source": "test",
            "provisional": True,
            "cases": {
                name: {"image_only": only, "required": name in REQUIRED}
                for name, only in SUITE_CASES.items()
            },
            "models": [
                {
                    "model_id": "vendor/model-1",
                    "provider": "openrouter",
                    "host": "openrouter.ai",
                    "date": "2026-10-04",
                    "reads_images": reads_images,
                    "note": "A note.",
                    "cases": cases,
                }
            ],
        }
    )


def _level(cases: dict[str, str], **kwargs: Any) -> Level:
    results = _results({**dict.fromkeys(SUITE_CASES, "pass"), **cases}, **kwargs)
    return verdict(results.models[0], results.cases).level


def test_every_case_passed_is_the_agent() -> None:
    """The top of the bar."""
    assert _level({}) is Level.AGENT


def test_one_failure_in_eight_stays_above_the_bar() -> None:
    """7 of 8 is 88%, over the 80% bar."""
    assert _level({"board-pack": "fail:did_not_say_assumption"}) is Level.AGENT


def test_three_failures_in_eight_are_near_the_bar() -> None:
    """Haiku 4.5's column: 5 of 8, the smoke and the demo passed."""
    failed = dict.fromkeys(
        ["memo-restructure", "spreadsheet-report", "board-pack"],
        "fail:skipped_preview_check",
    )
    assert _level(failed) is Level.AGENT_LIMITED


@pytest.mark.parametrize("case", ["smoke", "demo-flow"])
def test_failing_the_smoke_or_the_demo_is_studio_only(case: str) -> None:
    """Both must pass whatever the rest score."""
    assert _level({case: "fail"}) is Level.STUDIO_ONLY


@pytest.mark.parametrize("failure", ["made_no_document", "looped"])
def test_making_no_document_or_looping_is_studio_only_whatever_the_score(
    failure: str,
) -> None:
    """The agent cannot be left to work on its own."""
    assert _level({"board-pack": f"fail:{failure}"}) is Level.STUDIO_ONLY


def test_a_text_only_model_is_not_counted_on_the_cases_that_need_images() -> None:
    """GLM-5.3's column: n/a on the images case, the figure swap failed for want of images."""
    results = _results(
        {
            **dict.fromkeys(SUITE_CASES, "pass"),
            "images-reach-the-model": "n/a",
            "figure-swap": "fail:text_only",
        },
        reads_images=False,
    )

    found = verdict(results.models[0], results.cases)

    assert found.level is Level.AGENT
    assert (found.passed, found.counted) == (6, 6)


def test_a_case_the_gate_stopped_counts_as_not_passed() -> None:
    """A column stopped early has not shown it can do the rest."""
    stopped = dict.fromkeys(
        ["memo-restructure", "figure-swap", "board-pack", "spreadsheet-report"],
        "not_run",
    )
    assert _level(stopped) is Level.STUDIO_ONLY


def test_an_outcome_outside_the_format_is_refused() -> None:
    """A typo would otherwise count as a failure."""
    with pytest.raises(ValueError):
        _results({**dict.fromkeys(SUITE_CASES, "pass"), "smoke": "passed"})


def test_a_result_for_a_case_the_suite_does_not_hold_is_refused() -> None:
    """Every outcome is held to the suite it claims."""
    with pytest.raises(ValueError):
        _results({**dict.fromkeys(SUITE_CASES, "pass"), "extra-case": "pass"})


def test_a_pass_holds_only_where_it_was_measured_and_a_failure_everywhere() -> None:
    """A copy on this computer is the same model or a smaller one."""
    passed = measured_rows(_results(dict.fromkeys(SUITE_CASES, "pass")))
    failed = measured_rows(
        _results({**dict.fromkeys(SUITE_CASES, "pass"), "smoke": "fail"})
    )

    assert passed.models[0].match.served == ["remote"]
    assert failed.models[0].match.served == ["remote", "local"]


def test_the_shipped_list_is_what_the_generator_writes_from_the_committed_results() -> (
    None
):
    """Edited by the generators only, so a reviewer reads one diff: the results.

    The ladder's rows are its own; the screening sweep's sit after them.
    """
    committed = LadderResults.model_validate_json(
        COMMITTED_INPUT.read_text(encoding="utf-8")
    )
    shipped = CapabilityList.model_validate_json(SHIPPED.read_text(encoding="utf-8"))
    ladder = measured_rows(committed)

    assert with_ladder_rows(shipped, ladder) == shipped
    assert shipped.models[: len(ladder.models)] == ladder.models
    assert json.loads(SHIPPED.read_text(encoding="utf-8"))["schema_version"] == 1


def test_the_eleven_measured_models_land_where_08_puts_them() -> None:
    """08's matrices, through the bar."""
    levels = {
        row.key: row.level
        for row in measured_rows(
            LadderResults.model_validate_json(
                COMMITTED_INPUT.read_text(encoding="utf-8")
            )
        ).models
    }

    assert levels == {
        "claude-sonnet-5-5": "agent",
        "claude-opus-5-5": "agent",
        "claude-haiku-4-5": "agent_limited",
        "kimi-k3": "agent",
        "glm-5-3": "agent",
        "deepseek-v4-pro-0813": "agent",
        "qwen3-8-27b": "agent",
        "qwen3-6-35b-a3b": "studio_only",
        "gemma-4-31b-it": "studio_only",
        "ministral-14b-2512": "studio_only",
        "qwen3-5-9b": "studio_only",
    }
