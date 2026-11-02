"""A quoted answer is checked once more: a quote that is real but does not settle the question
leaves the answer to a person, so a related control never passes for the one asked about."""

import json
from pathlib import Path

import openpyxl
import pytest
from openpyxl.worksheet.datavalidation import DataValidation

from modules.artifacts.revised_copies.engines import excel
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
ISMS = SourceText(
    4,
    "isms",
    "## Review\n\nEvery policy is reviewed and approved by management each year.",
)
REVIEWED = "Every policy is reviewed and approved by management each year."


@pytest.fixture
def config(tmp_path: Path):
    """The runner's settings with the second check turned on for Yes."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    prompts = {
        "system": "system: $answers",
        "question": "$passages\n\nQuestion: $question",
        "repair": "$problem",
        "verify": "verify: $answer",
    }
    for name, text in prompts.items():
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
                "max_quotes": 2,
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
                    "quotes": [{"passage": 1, "quote": QUOTE}],
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
                "quotes": [{"passage": 1, "quote": QUOTE}],
                "answer": "Yes",
                "comment": "",
                "confidence": "high",
            }
        )
    )

    filled = fill_workbook(workbook, [PLAN], config, model)

    assert [r.answer for r in filled.results] == ["Needs review", "Needs review"]


def _reply(*quotes: str) -> ModelReply:
    return ModelReply(
        json.dumps(
            {
                "quotes": [{"passage": 1, "quote": q} for q in quotes],
                "answer": "Yes",
                "comment": "Planned and reviewed.",
                "confidence": "high",
            }
        )
    )


def test_an_answer_may_rest_on_quotes_from_two_documents(workbook, config, tmp_path):
    """Each quote is found in its own source, the second check reads them together, quotes past
    the job's limit are dropped, and the answers sheet gives each quote a line."""
    checks: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            checks.append(turns[0][1])
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        return _reply(QUOTE, REVIEWED, "A third quote, past the job's limit of two.")

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN, ISMS], config, model)

    contingency = filled.results[1]
    assert contingency.answer == "Yes"
    assert [(c.source, c.section) for c in contingency.cited] == [
        ("contingency-plan", "Plan"),
        ("isms", "Review"),
    ]
    assert '1. From contingency-plan: "The procedures' in checks[1]
    assert '2. From isms: "Every policy' in checks[1]
    assert "third quote" not in checks[1]
    out = tmp_path / "filled.xlsx"
    assert excel.apply(workbook, filled.operations, out).saved
    lines = [
        (row[1], row[6])
        for row in openpyxl.load_workbook(out)["Answers"].iter_rows(
            min_row=2, values_only=True
        )
    ]
    assert lines == [
        ("B2", "contingency-plan"),
        ("B2", "isms"),
        ("B3", "contingency-plan"),
        ("B3", "isms"),
    ]


def test_a_quote_that_is_not_in_any_source_is_named_when_the_answer_is_asked_again(
    workbook, config
):
    """The answer is checked on the quotes that were found; asked again, the model hears which was not."""
    turns_seen: list[list[tuple[str, str]]] = []
    verdicts = iter([False, True, False, True])

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            supported = next(verdicts)
            return ModelReply(
                json.dumps(
                    {
                        "supported": supported,
                        "missing": "" if supported else "Says nothing of review.",
                    }
                )
            )
        turns_seen.append(turns)
        if len(turns) == 1:
            return _reply(QUOTE, "Words that no policy of the firm holds anywhere.")
        return _reply(QUOTE, REVIEWED)

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN, ISMS], config, model)

    assert [r.answer for r in filled.results] == ["Yes", "Yes"]
    repair = turns_seen[1][-1][1]
    assert "Says nothing of review." in repair
    assert "Quote 2 is not, word for word, in any passage." in repair
    assert [c.source for c in filled.results[0].cited] == ["contingency-plan", "isms"]


@pytest.fixture
def looking_config(tmp_path: Path, config):
    """The same job, asking an answer that fell back to look once more."""
    folder = tmp_path / "job"
    (folder / "prompts" / "second_look.md").write_text(
        "Look again, part by part, or answer $fallback.", encoding="utf-8"
    )
    raw = json.loads((folder / "job.json").read_text(encoding="utf-8"))
    raw["second_look"] = {"prompt": "prompts/second_look.md"}
    (folder / "job.json").write_text(json.dumps(raw), encoding="utf-8")
    return load_config(folder / "job.json")


def test_an_answer_that_fell_back_is_asked_to_look_once_more(workbook, looking_config):
    """A second look may find the quote, which is then checked like any other; one that
    still falls back stays with a person."""
    asked: list[list[tuple[str, str]]] = []

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        asked.append(turns)
        looking = "Look again, part by part" in turns[-1][1]
        if looking and "contingency plan documented" in turns[0][1]:
            return _reply(QUOTE)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [],
                    "answer": "Needs review",
                    "comment": "Not settled.",
                    "confidence": "low",
                }
            )
        )

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], looking_config, model)

    virtualization, contingency = filled.results
    assert (contingency.answer, contingency.looked_again) == ("Yes", True)
    assert (virtualization.answer, virtualization.looked_again) == (
        "Needs review",
        True,
    )
    assert "Needs review." in asked[1][-1][1]
    assert len(asked) == 4


def test_a_pack_s_labels_set_the_standing_passages_apart():
    """The passages every question is shown come first, under the pack's label for them."""
    from modules.jobs.evidence.passages import passages_of
    from modules.jobs.workbook_rows.ask import passages_block

    passages = passages_of([PLAN, ISMS])

    block = passages_block(
        passages, [0, 1], [1], ("For all policies:", "For this one:")
    )

    assert block.index("For all policies:") < block.index("[2] isms")
    assert block.index("[2] isms") < block.index("For this one:")
    assert block.index("For this one:") < block.index("[1] contingency-plan")


def test_a_refused_answer_may_not_turn_into_another(workbook, config):
    """Refused, a Yes may find better evidence or give way; a switch to No goes to a person."""

    def ask(system, turns, schema, shared):
        if system.startswith("verify"):
            return ModelReply(json.dumps({"supported": False, "missing": "Off topic."}))
        if len(turns) == 1:
            return _reply(QUOTE)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [{"passage": 1, "quote": QUOTE}],
                    "answer": "No",
                    "comment": "",
                    "confidence": "high",
                }
            )
        )

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], config, model)

    result = filled.results[0]
    assert (result.answer, result.said) == ("Needs review", "Yes")
    assert result.codes == ["ANSWER_SWITCHED", "NEEDS_REVIEW"]
    assert [step["step"] for step in result.trace] == [
        "answer",
        "check",
        "after the check",
    ]


def test_a_fallback_that_says_why_is_not_asked_again(workbook, looking_config):
    """Only a doubtful fallback gets a second look: one that quotes nothing, is sure, and says
    what is open stays as it is."""
    asked: list[list[tuple[str, str]]] = []

    def ask(system, turns, schema, shared):
        asked.append(turns)
        return ModelReply(
            json.dumps(
                {
                    "quotes": [],
                    "answer": "Needs review",
                    "comment": "The plan says nothing of virtualization.",
                    "confidence": "high",
                }
            )
        )

    model = Model()
    model.ask = ask

    filled = fill_workbook(workbook, [PLAN], looking_config, model)

    assert [r.looked_again for r in filled.results] == [False, False]
    assert len(asked) == 2
