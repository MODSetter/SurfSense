"""An N/A that rests on a provider or a scope is not written but offered: a person confirms it in one
step, unless the firm has chosen to let a checked provider N/A be written. A second model may make
the checks."""

import json
from pathlib import Path

import openpyxl
import pytest
from openpyxl.worksheet.datavalidation import DataValidation

from modules.jobs.evidence.passages import SourceText
from modules.jobs.packs.manifest import PackRefusedError
from modules.jobs.workbook_rows.ask import ModelReply
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.decide import Cited, RowResult
from modules.jobs.workbook_rows.fill import fill_workbook
from modules.jobs.workbook_rows.layout import QuestionRow
from modules.jobs.workbook_rows.operations import (
    comment_text,
    exception_lines,
    operations,
    sheet_lines,
)

pytestmark = pytest.mark.unit

HOSTED = SourceText(
    7,
    "hosting",
    "## Hosting\n\nThe data centres are operated by Google Cloud, which runs their "
    "physical security.\n\n## Scope\n\nThis standard applies to laptops issued by the firm.",
)
PROVIDER = (
    "The data centres are operated by Google Cloud, which runs their physical security."
)
SCOPE = "This standard applies to laptops issued by the firm."


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """A job that suggests N/A on a provider or a scope, and declares the provider setting."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    for name, text in {
        "system": "system: $answers",
        "question": "$passages\n\nQuestion: $question",
        "repair": "$problem",
        "verify": "verify: $answer",
    }.items():
        (folder / "prompts" / f"{name}.md").write_text(text, encoding="utf-8")
    raw = {
        "answers": [
            {"answer": "Yes", "needs_quote": True},
            {"answer": "No", "needs_quote": True},
            {"answer": "N/A", "needs_quote": True},
            {"answer": "Needs review", "needs_quote": False, "fallback": True},
        ],
        "layout": {"question": ["question"], "answer": ["answer"]},
        "prompts": {
            "system": "prompts/system.md",
            "question": "prompts/question.md",
            "repair": "prompts/repair.md",
        },
        "verify": {"prompt": "prompts/verify.md", "answers": ["Yes", "No", "N/A"]},
        "templates": {"comment": {"*": "$comment"}, "evidence": "$where"},
        "sheets": {"answers": "Answers", "exceptions": "Exceptions"},
        "statement_gate": {
            "answers": ["No", "N/A"],
            "quote": r"\b(applies to|operated by|provided by)\b",
            "comment": r"\bdocuments?\b[^.]{0,40}\bdo(es)?\s+not\s+state",
            "suggest": ["N/A"],
            "provider": r"\b(operated by|provided by)\b",
            "provider_setting": "provider_na",
        },
        "settings": [
            {
                "key": "provider_na",
                "label": "Treat provider-run controls as N/A",
                "default": False,
            }
        ],
    }
    (folder / "job.json").write_text(json.dumps(raw), encoding="utf-8")
    return folder / "job.json"


@pytest.fixture
def config(config_file: Path):
    """The job, loaded as a run loads it."""
    return load_config(config_file)


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    """One question whose dropdown offers Yes, No and N/A."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Question", "Answer"])
    sheet.append(["Is physical access to the data centre controlled?", None])
    rule = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
    rule.add("B2")
    sheet.add_data_validation(rule)
    path = tmp_path / "Q.xlsx"
    book.save(path)
    return path


class Scripted:
    """Answers with one reply; a check says `supported`. Records which calls it got."""

    window = 32_768
    concurrency = 1

    def __init__(
        self, reply: ModelReply | None = None, supported: bool = True, name="answers"
    ):
        self.name = name
        self.reply = reply
        self.supported = supported
        self.answers: list[str] = []
        self.checks: list[str] = []

    def ask(self, system, turns, schema, shared):
        if system.startswith("verify"):
            self.checks.append(turns[0][1])
            return ModelReply(
                json.dumps(
                    {
                        "supported": self.supported,
                        "missing": "" if self.supported else "Says nothing of access.",
                    }
                )
            )
        self.answers.append(turns[-1][1])
        return self.reply


def _reply(
    answer: str, quote: str, comment: str = "Run by our provider."
) -> ModelReply:
    return ModelReply(
        json.dumps(
            {
                "quotes": [{"passage": 1, "quote": quote}],
                "answer": answer,
                "comment": comment,
                "confidence": "high",
            }
        )
    )


def _one(workbook, config, model, **kwargs):
    return fill_workbook(workbook, [HOSTED], config, model, **kwargs).results[0]


def test_a_provider_run_n_a_is_suggested_with_its_evidence(workbook, config):
    """The checked N/A is not written: the cell is left to a person, and the comment and the
    exceptions sheet say what to confirm and where its evidence is."""
    model = Scripted(_reply("N/A", PROVIDER))

    result = _one(workbook, config, model)

    assert (result.answer, result.said, result.suggested) == (
        "Needs review",
        "N/A",
        "N/A",
    )
    assert result.written is None and result.codes[0] == "SUGGESTED"
    assert len(model.checks) == 1
    assert comment_text(result, config) == (
        f'Suggested: N/A. Evidence: hosting, Hosting: "{PROVIDER}"'
    )
    why = exception_lines([result], [])[0][4]
    assert why.startswith("The checks support N/A") and PROVIDER in why


def test_the_firm_s_provider_setting_writes_a_checked_provider_n_a(workbook, config):
    """With the setting on, the checked N/A is written like any answer, and the run says so."""
    model = Scripted(_reply("N/A", PROVIDER))

    filled = fill_workbook(
        workbook, [HOSTED], config, model, settings={"provider_na": True}
    )
    result = filled.results[0]

    assert (result.answer, result.written, result.suggested) == ("N/A", "N/A", None)
    assert "SUGGESTED" not in result.codes and len(model.checks) == 1
    assert filled.settings == {"provider_na": True}


@pytest.mark.parametrize("provider_na", [False, True])
def test_a_provider_n_a_the_check_refuses_is_neither_written_nor_suggested(
    workbook, config, provider_na
):
    """A refused check leaves the row to a person with the check's reason, whatever the setting."""
    model = Scripted(_reply("N/A", PROVIDER), supported=False)

    result = _one(workbook, config, model, settings={"provider_na": provider_na})

    assert (result.answer, result.said, result.suggested) == (
        "Needs review",
        "N/A",
        None,
    )
    assert result.codes[0] == "NOT_SUPPORTED"
    assert result.missing == "Says nothing of access."


def test_an_n_a_on_a_scope_is_only_ever_suggested(workbook, config):
    """The provider setting writes only what a provider runs: an N/A resting on a scope stays
    a suggestion with the setting on."""
    model = Scripted(_reply("N/A", SCOPE))

    result = _one(workbook, config, model, settings={"provider_na": True})

    assert (result.answer, result.suggested) == ("Needs review", "N/A")
    assert result.codes[0] == "SUGGESTED"


def test_a_no_resting_on_a_provider_is_never_suggested(workbook, config):
    """Only the answers a pack lets the job suggest are offered: a No on a provider quote goes
    to a person unchecked, as before."""
    model = Scripted(_reply("No", PROVIDER))

    result = _one(workbook, config, model, settings={"provider_na": True})

    assert result.codes[0] == "NO_STATEMENT" and result.suggested is None
    assert model.checks == []


def test_a_provider_quote_outweighs_a_comment_about_silence(workbook, config):
    """The quote naming the provider is a statement, so the N/A is checked and suggested even
    when the model's comment also says what the documents leave out."""
    model = Scripted(
        _reply(
            "N/A",
            PROVIDER,
            comment="The documents do not state that the firm controls access itself.",
        )
    )

    result = _one(workbook, config, model)

    assert result.codes[0] == "SUGGESTED" and len(model.checks) == 1


def test_an_n_a_resting_on_silence_alone_is_not_suggested(workbook, config):
    """Silence is never evidence: no check is asked and nothing is offered."""
    silent = SourceText(
        8, "silent", "## Rules\n\nStaff must lock their screens when away from them."
    )
    model = Scripted(
        _reply(
            "N/A",
            "Staff must lock their screens when away from them.",
            comment="The documents do not state anything about data centres.",
        )
    )

    result = fill_workbook(workbook, [silent], config, model).results[0]

    assert result.codes[0] == "NO_STATEMENT" and result.suggested is None
    assert model.checks == []


def test_a_second_model_makes_the_checks(workbook, config):
    """With a checker, the answering model is never asked to check, and the checker never
    answers."""
    model = Scripted(_reply("Yes", PROVIDER, comment="Access is controlled."))
    checker = Scripted(name="checker")

    result = _one(workbook, config, model, checker=checker)

    assert result.answer == "Yes"
    assert model.checks == [] and len(checker.checks) == 1
    assert checker.answers == []


@pytest.mark.parametrize(
    ("settings", "why"),
    [({"nope": True}, "no setting nope"), ({"provider_na": "yes"}, "true or false")],
)
def test_a_setting_the_job_does_not_take_is_refused(workbook, config, settings, why):
    """A setting the job does not declare, or a value that is not true or false, stops the run."""
    with pytest.raises(ValueError, match=why):
        fill_workbook(workbook, [HOSTED], config, Scripted(), settings=settings)


def test_a_gate_whose_setting_is_not_declared_refuses_the_pack(config_file: Path):
    """A gate that names a setting the pack does not declare is a broken pack."""
    raw = json.loads(config_file.read_text(encoding="utf-8"))
    raw["settings"] = []
    config_file.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(PackRefusedError) as refused:
        load_config(config_file)

    assert refused.value.code == "BAD_JOB_CONFIG"
    assert "provider_na" in refused.value.message


def test_each_row_s_lines_are_found_where_the_sheets_put_them(config):
    """Confirming edits a row's lines on the added sheets by position: the positions must be
    the ones the sheets were written with, for rows with several quotes, codes or none."""

    def row(number: int) -> QuestionRow:
        return QuestionRow(
            "Q", number, "Q?", f"A{number}", f"B{number}", None, None, "", None
        )

    cited = [Cited(f"quote {n}", "policy", "", n) for n in range(3)]
    results = [
        RowResult(row(2), "Yes", None, "Yes", "", "high", cited=cited[:2]),
        RowResult(
            row(3),
            "Needs review",
            "N/A",
            None,
            "",
            "low",
            codes=["SUGGESTED", "NEEDS_REVIEW"],
        ),
        RowResult(row(4), "Yes", None, "Yes", "", "high", cited=cited[2:]),
        RowResult(
            row(5), "Needs review", None, None, "", "low", codes=["NEEDS_REVIEW"]
        ),
    ]

    ops = operations(results, [], config, ["Q"])
    answers, exceptions = (op["values"] for op in ops if op["op"] == "add_sheet")
    lines = sheet_lines(results)

    for result, line in zip(results, lines, strict=True):
        first, last = line["answers"]
        held = answers[first - 1 : last]
        assert len(held) == max(len(result.cited), 1)
        assert {v[1] for v in held} == {result.row.answer_cell}
        if result.codes:
            first, last = line["exceptions"]
            listed = exceptions[first - 1 : last]
            assert len(listed) == len(result.codes)
            assert {v[1] for v in listed} == {result.row.answer_cell}
        else:
            assert line["exceptions"] is None
    assert lines[-1]["answers"][1] == len(answers)
    assert lines[-1]["exceptions"][1] == len(exceptions)


def test_a_suggestion_is_checked_by_the_gate_s_own_prompt(workbook, config_file):
    """With its own check, the gate leaves the main check's wording to every other answer:
    rewording that check cost right answers on rows nothing to do with N/A."""
    folder = config_file.parent
    (folder / "prompts" / "provider_check.md").write_text(
        "provider check: $answer", encoding="utf-8"
    )
    raw = json.loads(config_file.read_text(encoding="utf-8"))
    raw["statement_gate"]["check"] = "prompts/provider_check.md"
    config_file.write_text(json.dumps(raw), encoding="utf-8")
    config = load_config(config_file)
    systems: list[str] = []

    def ask(system, turns, schema, shared):
        if system.startswith(("verify", "provider check")):
            systems.append(system)
            return ModelReply(json.dumps({"supported": True, "missing": ""}))
        answer = "N/A" if len(systems) == 0 else "Yes"
        return _reply(answer, PROVIDER)

    model = Scripted()
    model.ask = ask
    suggested = _one(workbook, config, model)
    written = _one(workbook, config, model)

    assert (suggested.suggested, written.answer) == ("N/A", "Yes")
    assert systems == ["provider check: N/A", "verify: Yes"]
