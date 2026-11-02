"""The workbook-rows runner answers each question from the sources, never writes an answer its
quote does not support, and writes only values the cell's dropdown offers."""

import json
from pathlib import Path

import openpyxl
import pytest
from openpyxl.worksheet.datavalidation import DataValidation

from modules.artifacts.revised_copies.engines import excel
from modules.artifacts.revised_copies.engines.excel_inspection import inspect_workbook
from modules.jobs.evidence.passages import SourceText
from modules.jobs.workbook_rows.ask import ModelReply
from modules.jobs.workbook_rows.config import load_config
from modules.jobs.workbook_rows.fill import fill_workbook
from modules.jobs.workbook_rows.layout import find_questions

pytestmark = pytest.mark.unit

POLICY = SourceText(
    7,
    "Security plan",
    "## Access\n\nAccess to client data is granted on a least-privilege basis.\n\n"
    "## Media\n\nDrives are wiped with a NIST 800-88 method before disposal.",
)


@pytest.fixture
def config(tmp_path: Path):
    """The runner's settings as a pack brings them, with stand-in prompts."""
    folder = tmp_path / "job"
    (folder / "prompts").mkdir(parents=True)
    for name, text in {
        "system.md": "Answer with one of $answers.",
        "question.md": "$passages\n\nQuestion: $question ($context)",
        "repair.md": "$problem",
    }.items():
        (folder / "prompts" / name).write_text(text, encoding="utf-8")
    (folder / "job.json").write_text(
        json.dumps(
            {
                "answers": [
                    {"answer": "Yes", "needs_quote": True, "cell_values": ["Yes"]},
                    {"answer": "No", "needs_quote": True, "cell_values": ["No"]},
                    {
                        "answer": "N/A",
                        "needs_quote": True,
                        "cell_values": ["N/A", "NA"],
                    },
                    {"answer": "Needs review", "needs_quote": False, "fallback": True},
                ],
                "layout": {
                    "question": ["question"],
                    "answer": ["answer", "response"],
                    "comment": ["comments"],
                    "evidence": ["evidence"],
                    "context": ["topic", "#"],
                },
                "prompts": {
                    "system": "prompts/system.md",
                    "question": "prompts/question.md",
                    "repair": "prompts/repair.md",
                },
                "templates": {
                    "comment": {
                        "Needs review": "Needs review: $comment",
                        "*": '$comment "$quote"',
                    },
                    "evidence": "$where",
                },
                "sheets": {
                    "answers": "SurfSense answers",
                    "exceptions": "SurfSense exceptions",
                },
            }
        ),
        encoding="utf-8",
    )
    return load_config(folder / "job.json")


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    """A requester's questionnaire: a section row, three open questions and one already answered."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Questionnaire"
    sheet.append(["#", "Topic", "Question", "Answer", "Comments", "Evidence"])
    sheet.append([None, None, "Access control", None, None, None])
    sheet.append(
        [1, "Access", "Do users have the minimum access they need?", None, None, None]
    )
    sheet.append(
        [2, "Media", "Is storage media wiped before disposal?", None, None, None]
    )
    sheet.append(
        [3, "History", "Have you had a breach in the last year?", None, None, None]
    )
    sheet.append([4, "Access", "Is access reviewed every quarter?", "Yes", None, None])
    rule = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
    rule.add("D3:D6")
    sheet.add_data_validation(rule)
    path = tmp_path / "Questionnaire.xlsx"
    book.save(path)
    return path


class ScriptedModel:
    """Replies in order, one per call, and keeps what it was asked."""

    name = "scripted"
    window = 32_768
    concurrency = 1

    def __init__(self, replies: dict[str, list[dict | str]]):
        self.replies = replies
        self.asked: list[list[tuple[str, str]]] = []

    def ask(self, system, turns, schema, shared):
        self.asked.append(turns)
        asked_about = turns[0][1].split("Question:")[-1]
        question = next(q for q in self.replies if q in asked_about)
        reply = self.replies[question].pop(0)
        return ModelReply(
            reply if isinstance(reply, str) else json.dumps(reply), 100, 20
        )


def draft(
    answer, quote="", passage=1, comment="Stated in the plan.", confidence="high"
):
    """A model's reply for one row."""
    return {
        "passage": passage,
        "quote": quote,
        "answer": answer,
        "comment": comment,
        "confidence": confidence,
    }


def test_the_layout_skips_section_rows_and_answered_rows_and_reads_each_dropdown(
    workbook, config
):
    """The finder takes the question and answer columns from the headers, skips section and answered rows, and reads each row's dropdown and context."""
    layout = find_questions(inspect_workbook(workbook), config.layout)

    [table] = layout.tables
    assert (table.question_column, table.answer_column) == (3, 4)
    assert [row.row for row in layout.rows] == [3, 4, 5]
    assert layout.rows[0].allowed == ("Yes", "No", "N/A")
    assert layout.rows[0].context == "Section: Access control; #: 1; Topic: Access"
    assert [(s.row, s.code) for s in layout.skipped] == [(6, "ALREADY_ANSWERED")]


def test_supported_answers_are_written_and_an_unsupported_yes_becomes_needs_review(
    workbook, config, tmp_path
):
    """A quoted Yes is written with its source; a Yes whose quote is in no source is asked again, then left blank as Needs review with its exceptions."""
    model = ScriptedModel(
        {
            "minimum access": [
                draft(
                    "Yes",
                    "Access to client data is granted on a least-privilege basis.",
                )
            ],
            "wiped": [
                draft("Yes", "Drives are shredded before disposal."),
                draft("Yes", "Drives are always shredded."),
            ],
            "breach": [
                draft("Needs review", comment="The plan says nothing of past breaches.")
            ],
        }
    )

    filled = fill_workbook(workbook, [POLICY], config, model)

    access, media, breach = filled.results
    assert (access.answer, access.written, access.source, access.section) == (
        "Yes",
        "Yes",
        "Security plan",
        "Access",
    )
    assert (media.answer, media.said, media.written) == ("Needs review", "Yes", None)
    assert media.codes == ["QUOTE_NOT_FOUND", "NEEDS_REVIEW"]
    assert media.calls == 2 and "not, word for word" in model.asked[2][-1][1]
    assert (breach.answer, breach.written, breach.codes) == (
        "Needs review",
        None,
        ["NEEDS_REVIEW"],
    )
    assert filled.counts == {"Yes": 1, "Needs review": 2, "blank": 2, "skipped": 1}

    out = tmp_path / "filled.xlsx"
    report = excel.apply(workbook, filled.operations, out)
    assert report.saved
    opened = openpyxl.load_workbook(out)
    sheet = opened["Questionnaire"]
    assert [sheet[f"D{r}"].value for r in range(3, 7)] == ["Yes", None, None, "Yes"]
    assert sheet["F3"].value == "Security plan, Access"
    assert sheet["E5"].value == "Needs review: The plan says nothing of past breaches."
    assert opened.sheetnames == [
        "Questionnaire",
        "SurfSense answers",
        "SurfSense exceptions",
    ]
    exceptions = [
        row[1]
        for row in opened["SurfSense exceptions"].iter_rows(min_row=2, values_only=True)
    ]
    assert exceptions == ["D4", "D4", "D5", "D6"]
    assert inspect_workbook(out).sheet("Questionnaire").dropdown_at("D4").values == (
        "Yes",
        "No",
        "N/A",
    )


def test_a_reply_that_is_not_json_is_asked_again_then_left_for_review(workbook, config):
    """A reply that holds no answer is asked again once, then left for a person."""
    model = ScriptedModel(
        {
            "minimum access": ["I think yes.", "Still yes."],
            "wiped": [draft("Needs review")],
            "breach": [draft("Needs review")],
        }
    )

    filled = fill_workbook(workbook, [POLICY], config, model)

    assert filled.results[0].codes == ["UNREADABLE_REPLY", "NEEDS_REVIEW"]
    assert filled.results[0].calls == 2


def test_only_the_rows_asked_for_are_answered(workbook, config):
    """An eval can answer only its gold rows."""
    model = ScriptedModel({"wiped": [draft("Needs review")]})

    filled = fill_workbook(
        workbook, [POLICY], config, model, only=lambda row: row.row == 4
    )

    assert [r.row.row for r in filled.results] == [4]
