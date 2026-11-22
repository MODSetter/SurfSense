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
from modules.jobs.workbook_rows.fill import NoQuestionsError, fill_workbook
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
    """A model's reply for one row, with one quote or none."""
    return {
        "quotes": [{"passage": passage, "quote": quote}] if quote else [],
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


def test_the_total_is_reported_before_the_first_question(workbook, config):
    """The screen can say how many questions there are while the sources are still being
    read, and the last count is every one."""
    model = ScriptedModel(
        {
            "minimum access": [
                draft(
                    "Yes",
                    "Access to client data is granted on a least-privilege basis.",
                )
            ],
            "wiped": [draft("Needs review")],
            "breach": [draft("Needs review")],
        }
    )
    counted: list[tuple[int, int, int]] = []

    fill_workbook(
        workbook,
        [POLICY],
        config,
        model,
        on_row=lambda done, total: counted.append((done, total, len(model.asked))),
    )

    assert counted[0] == (0, 3, 0)
    assert counted[-1] == (3, 3, 3)


def test_a_workbook_without_questions_is_refused_before_any_embedding(tmp_path, config):
    """A sheet of figures has nothing to answer: the run says what a questionnaire needs
    instead of embedding the sources for nothing."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Item", "Cost"])
    sheet.append(["Pilot", 12000])
    path = tmp_path / "Pricing.xlsx"
    book.save(path)
    embedded: list[list[str]] = []

    def embed(texts: list[str], query: bool) -> list[list[float]]:
        embedded.append(texts)
        return [[1.0] for _ in texts]

    with pytest.raises(NoQuestionsError, match="found no questions in this workbook"):
        fill_workbook(path, [POLICY], config, ScriptedModel({}), embed=embed)

    assert embedded == []


def test_only_the_rows_asked_for_are_answered(workbook, config):
    """An eval can answer only its gold rows."""
    model = ScriptedModel({"wiped": [draft("Needs review")]})

    filled = fill_workbook(
        workbook, [POLICY], config, model, only=lambda row: row.row == 4
    )

    assert [r.row.row for r in filled.results] == [4]


def test_a_context_cell_merged_down_its_rows_reaches_every_row(tmp_path, config):
    """A control's topic, merged down all of its question rows, is in each row's context, as
    CAIQ's control title and specification are, not only in the merge's first row."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["#", "Topic", "Question", "Answer"])
    sheet.append(
        ["1", "Business continuity exercises", "Is the exercise run each year?", None]
    )
    sheet.append(["2", None, "Are the results of the exercise reported?", None])
    sheet.append(["3", None, "Is the exercise scope approved by management?", None])
    sheet.merge_cells("B2:B4")
    rule = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
    rule.add("D2:D4")
    sheet.add_data_validation(rule)
    path = tmp_path / "Merged.xlsx"
    book.save(path)

    layout = find_questions(inspect_workbook(path), config.layout)

    assert [row.context for row in layout.rows] == [
        f"#: {n}; Topic: Business continuity exercises" for n in (1, 2, 3)
    ]


def test_a_comment_cell_merged_down_its_rows_is_written_only_in_its_first_row(
    tmp_path, config
):
    """The engine writes a merge only at its first cell, so the rows a comment cell's merge
    covers below it get no comment, and the copy still saves."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Question", "Answer", "Comments"])
    sheet.append(["Do users have the minimum access they need?", None, None])
    sheet.append(["Is storage media wiped before disposal?", None, None])
    sheet.append(["Have you had a breach in the last year?", None, None])
    sheet.merge_cells("C2:C4")
    rule = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
    rule.add("B2:B4")
    sheet.add_data_validation(rule)
    path = tmp_path / "Merged comments.xlsx"
    book.save(path)
    model = ScriptedModel(
        {
            "minimum access": [draft("Needs review")],
            "wiped": [draft("Needs review")],
            "breach": [draft("Needs review")],
        }
    )

    layout = find_questions(inspect_workbook(path), config.layout)
    filled = fill_workbook(path, [POLICY], config, model)

    assert [row.comment_cell for row in layout.rows] == ["C2", None, None]
    assert excel.apply(path, filled.operations, tmp_path / "filled.xlsx").saved


def test_a_hidden_answer_column_is_not_answered_though_it_comes_first(tmp_path, config):
    """A hidden column of dropdowns under an answer header, such as a scoring helper's, is not
    where the requester reads the answers: the visible one is answered."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Question", "Answer", "Response"])
    for question in ("Is access reviewed?", "Is media wiped?", "Is data encrypted?"):
        sheet.append([f"{question} Say how often.", None, None])
    for column in "BC":
        rule = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
        rule.add(f"{column}2:{column}4")
        sheet.add_data_validation(rule)
    sheet.column_dimensions["B"].hidden = True
    path = tmp_path / "Hidden answers.xlsx"
    book.save(path)

    layout = find_questions(inspect_workbook(path), config.layout)

    assert [row.answer_cell for row in layout.rows] == ["C2", "C3", "C4"]


def test_a_hidden_column_with_more_dropdowns_loses_to_the_visible_one(tmp_path, config):
    """In a table found by its dropdowns, a hidden column covering more rows is not the
    answers."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Security controls"])
    for question in ("Is access reviewed?", "Is media wiped?", "Is data encrypted?"):
        sheet.append([f"{question} Say how often.", None, None])
    answers = DataValidation(type="list", formula1='"Yes,No,N/A"', allow_blank=True)
    answers.add("B2:B4")
    scores = DataValidation(type="list", formula1='"0,1,2"', allow_blank=True)
    scores.add("C2:C1000")
    for rule in (answers, scores):
        sheet.add_data_validation(rule)
    sheet.column_dimensions["C"].hidden = True
    path = tmp_path / "Hidden scores.xlsx"
    book.save(path)

    layout = find_questions(inspect_workbook(path), config.layout)

    assert [row.answer_cell for row in layout.rows] == ["B2", "B3", "B4"]
