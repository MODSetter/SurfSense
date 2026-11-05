"""The job eval's scoring of suggested answers: a suggestion scores as the person's blank, is
counted apart when its cell can hold it, and each run is also scored with the firm's provider
setting the other way round, which changes only how a checked provider answer ends."""

import json
from pathlib import Path

import pytest
from job_eval.cases import Case, GoldRow
from job_eval.score import score_case

from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.decide import Cited, RowResult
from modules.jobs.workbook_rows.layout import QuestionRow

pytestmark = pytest.mark.unit

WITH_NA = ("Yes", "No", "N/A")
WITHOUT_NA = ("Yes", "No")


@pytest.fixture
def config(tmp_path: Path):
    """Yes, No, N/A and the fallback, as the questionnaire job answers."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    for name in ("system", "question", "repair"):
        (folder / "prompts" / f"{name}.md").write_text(name, encoding="utf-8")
    (folder / "job.json").write_text(
        json.dumps(
            {
                "answers": [
                    {"answer": "Yes"},
                    {"answer": "No"},
                    {"answer": "N/A"},
                    {"answer": "Needs review", "needs_quote": False, "fallback": True},
                ],
                "layout": {"question": ["question"], "answer": ["answer"]},
                "prompts": {
                    "system": "prompts/system.md",
                    "question": "prompts/question.md",
                    "repair": "prompts/repair.md",
                },
                "templates": {"comment": {"*": "$comment"}, "evidence": "$where"},
                "sheets": {"answers": "A", "exceptions": "E"},
            }
        ),
        encoding="utf-8",
    )
    return load_config(folder / "job.json")


def _row(cell: str, allowed: tuple[str, ...]) -> QuestionRow:
    return QuestionRow(
        "Q", int(cell[1:]), "Q?", f"A{cell[1:]}", cell, None, None, "", allowed
    )


def _gated(kind: str) -> list[dict]:
    return [{"step": "answer"}, {"step": "statement gate", "kind": kind}]


def _suggested(cell: str, kind: str, allowed=WITH_NA) -> RowResult:
    result = RowResult(
        _row(cell, allowed),
        "Needs review",
        "N/A",
        None,
        "",
        "high",
        codes=["SUGGESTED", "NEEDS_REVIEW"],
    )
    result.suggested, result.trace = "N/A", _gated(kind)
    result.cited = [Cited("Hosted by the provider.", "policy", "", 1)]
    return result


def _case(*gold: tuple[str, str]) -> Case:
    rows = tuple(GoldRow("Q", cell, "Q?", answer, "") for cell, answer in gold)
    return Case("c", "c", "job", Path("q.xlsx"), (), rows, "draft", Path("."))


def test_a_provider_suggestion_is_the_blank_as_run_and_the_answer_with_the_setting(
    config,
):
    """Off, the suggested N/A scores as the person's blank and as one right suggestion; with the
    setting the other way round it would have been written, and right."""
    scored = score_case(_case(("B2", "N/A")), [_suggested("B2", "provider")], config)

    (row,) = scored.rows
    assert (row.answer, row.correct, row.confirmable) == ("Needs review", False, True)
    assert (row.answer_flipped, row.correct_flipped) == ("N/A", True)
    assert (scored.suggested_right, scored.suggested_wrong) == (1, 0)


def test_a_scope_suggestion_stays_a_suggestion_with_the_setting(config):
    """The setting writes only what a provider runs: a scope suggestion is the blank either way."""
    scored = score_case(_case(("B2", "N/A")), [_suggested("B2", "scope")], config)

    assert scored.rows[0].answer_flipped == "Needs review"
    assert scored.correct_flipped == 0


def test_a_provider_n_a_the_setting_wrote_would_have_been_suggested(config):
    """Run with the setting on, the checked provider N/A was written; the other way round it
    would have been the blank."""
    written = RowResult(_row("B2", WITH_NA), "N/A", None, "N/A", "", "high")
    written.trace = _gated("provider")

    scored = score_case(_case(("B2", "N/A")), [written], config, provider_on=True)

    (row,) = scored.rows
    assert (row.correct, row.answer_flipped, row.correct_flipped) == (
        True,
        "Needs review",
        False,
    )


def test_a_refused_provider_n_a_is_the_blank_either_way(config):
    """A provider N/A the check refused is neither written nor suggested, whatever the setting."""
    refused = RowResult(
        _row("B2", WITH_NA),
        "Needs review",
        "N/A",
        None,
        "",
        "high",
        codes=["NOT_SUPPORTED", "NEEDS_REVIEW"],
    )
    refused.trace = _gated("provider")

    for provider_on in (False, True):
        scored = score_case(
            _case(("B2", "Needs review")), [refused], config, provider_on
        )
        assert scored.rows[0].answer_flipped == "Needs review"
        assert scored.correct_flipped == 1


def test_a_suggestion_its_cell_cannot_hold_is_not_one_step_away(config):
    """A dropdown without N/A cannot take the suggestion: it is counted neither right nor wrong,
    and with the setting the other way round the cell would still be blank."""
    scored = score_case(
        _case(("B2", "N/A")), [_suggested("B2", "provider", allowed=WITHOUT_NA)], config
    )

    (row,) = scored.rows
    assert not row.confirmable and row.answer_flipped == "Needs review"
    assert (scored.suggested_right, scored.suggested_wrong) == (0, 0)
    assert row.correct and row.correct_flipped  # the gold N/A expects the blank here
