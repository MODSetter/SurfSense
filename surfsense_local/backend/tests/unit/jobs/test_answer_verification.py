"""A quoted answer is checked once more: a quote that is real but does not settle the question
leaves the answer to a person, so a related control never passes for the one asked about."""

import json
from pathlib import Path

import openpyxl
import pytest
from openpyxl.worksheet.datavalidation import DataValidation

from modules.jobs.evidence.passages import SourceText
from modules.jobs.workbook_rows.ask import ModelReply
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.fill import fill_workbook

pytestmark = pytest.mark.unit

PLAN = SourceText(
    3,
    "contingency-plan",
    "## Plan\n\nThe procedures shall be documented in a formal contingency plan.",
)
QUOTE = "The procedures shall be documented in a formal contingency plan."


@pytest.fixture
def config(tmp_path: Path):
    """The runner's settings with the second check turned on for Yes."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    for name in ("system", "question", "repair", "verify"):
        text = (
            "$passages\n\nQuestion: $question"
            if name == "question"
            else f"{name}: $answer"
        )
        (folder / "prompts" / f"{name}.md").write_text(text, encoding="utf-8")
    (folder / "job.json").write_text(
        json.dumps(
            {
                "answers": [
                    {"answer": "Yes", "needs_quote": True},
                    {"answer": "No", "needs_quote": True},
                    {"answer": "Needs review", "needs_quote": False, "fallback": True},
                ],
                "layout": {"question": ["question"], "answer": ["answer"]},
                "prompts": {
                    "system": "prompts/system.md",
                    "question": "prompts/question.md",
                    "repair": "prompts/repair.md",
                },
                "verify": {"prompt": "prompts/verify.md", "answers": ["Yes"]},
                "templates": {"comment": {"*": "$comment"}, "evidence": "$where"},
                "sheets": {"answers": "Answers", "exceptions": "Exceptions"},
            }
        ),
        encoding="utf-8",
    )
    return load_config(folder / "job.json")


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    """Two questions with a Yes/No dropdown."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Question", "Answer"])
    sheet.append(["Are virtualization security policies established?", None])
    sheet.append(["Is a contingency plan documented?", None])
    rule = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    rule.add("B2:B3")
    sheet.add_data_validation(rule)
    path = tmp_path / "Q.xlsx"
    book.save(path)
    return path


class Model:
    """Answers Yes with the plan's one sentence; the second check holds only for the contingency plan."""

    name = "scripted"
    window = 32_768
    concurrency = 1

    def __init__(self) -> None:
        self.checks: list[str] = []

    def ask(self, system, turns, schema, shared):
        question = turns[0][1].split("Question:")[-1]
        if system.startswith("verify"):
            self.checks.append(question)
            settled = "contingency plan documented" in question
            return ModelReply(
                json.dumps(
                    {
                        "supported": settled,
                        "missing": "" if settled else "Says nothing of virtualization.",
                    }
                )
            )
        return ModelReply(
            json.dumps(
                {
                    "passage": 1,
                    "quote": QUOTE,
                    "answer": "Yes",
                    "comment": "Planned.",
                    "confidence": "high",
                }
            )
        )


def test_a_real_quote_that_does_not_settle_the_question_is_left_for_review(
    workbook, config
):
    """The verified Yes stands; the Yes resting on an unrelated sentence is asked again, then becomes Needs review with what is missing."""
    model = Model()

    filled = fill_workbook(workbook, [PLAN], config, model)

    virtualization, contingency = filled.results
    assert (contingency.answer, contingency.written) == ("Yes", "Yes")
    assert (virtualization.answer, virtualization.said, virtualization.written) == (
        "Needs review",
        "Yes",
        None,
    )
    assert virtualization.codes == ["NOT_SUPPORTED", "NEEDS_REVIEW"]
    assert "virtualization" in filled.exceptions[0][4]
    # The refused answer is asked once more with the reason, and checked again.
    assert len(model.checks) == 3


def test_a_check_that_cannot_be_read_does_not_let_the_answer_through(workbook, config):
    """An unreadable second check counts as unsupported: the answer goes to a person."""
    model = Model()
    model.ask = lambda system, turns, schema, shared: ModelReply(
        "not json"
        if system.startswith("verify")
        else json.dumps(
            {
                "passage": 1,
                "quote": QUOTE,
                "answer": "Yes",
                "comment": "",
                "confidence": "high",
            }
        )
    )

    filled = fill_workbook(workbook, [PLAN], config, model)

    assert [r.answer for r in filled.results] == ["Needs review", "Needs review"]
