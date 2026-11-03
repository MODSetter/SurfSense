"""The revise engine's operations for a filled questionnaire: each answer in its own cell, a comment
and a source where the requester left room for them, then a sheet of every answer's sources (a
line per quote) and a sheet of the exceptions, after the requester's own."""

from __future__ import annotations

from dataclasses import replace
from string import Template

from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.decide import (
    EXCEPTIONS,
    RowResult,
    template_fields,
    written_value,
)
from modules.jobs.workbook_rows.layout import Skipped

ANSWER_COLUMNS = (
    "Sheet",
    "Cell",
    "Question",
    "Answer",
    "Written in the cell",
    "Confidence",
    "Source",
    "Section",
    "Line",
    "Quote",
    "Comment",
)
EXCEPTION_COLUMNS = ("Sheet", "Cell", "Question", "Answer", "Why a person should look")


def operations(
    results: list[RowResult],
    skipped: list[Skipped],
    config: JobConfig,
    taken_sheets: list[str],
) -> list[dict]:
    ops: list[dict] = []
    for result in results:
        row = result.row
        if result.written is not None:
            ops.append(_set(row.sheet, row.answer_cell, result.written))
        comment = comment_text(result, config)
        if row.comment_cell and comment:
            ops.append(_set(row.sheet, row.comment_cell, comment))
        evidence = evidence_text(result, config)
        if row.evidence_cell and evidence:
            ops.append(_set(row.sheet, row.evidence_cell, evidence))
    labels = config.labels
    ops.append(
        {
            "op": "add_sheet",
            "sheet": _free_name(config.answers_sheet, taken_sheets),
            "values": [
                [labels.get(c, c) for c in ANSWER_COLUMNS],
                *[line for r in results for line in _answer_lines(r)],
            ],
        }
    )
    ops.append(
        {
            "op": "add_sheet",
            "sheet": _free_name(config.exceptions_sheet, taken_sheets),
            "values": [
                [labels.get(c, c) for c in EXCEPTION_COLUMNS],
                *exception_lines(results, skipped),
            ],
        }
    )
    return ops


def comment_text(result: RowResult, config: JobConfig) -> str:
    templates = config.templates.comment
    template = templates.get(result.answer) or templates.get("*") or ""
    return " ".join(Template(template).safe_substitute(template_fields(result)).split())


def evidence_text(result: RowResult, config: JobConfig) -> str:
    if not result.source:
        return ""
    return " ".join(
        Template(config.templates.evidence)
        .safe_substitute(template_fields(result))
        .split()
    )


def exception_lines(
    results: list[RowResult], skipped: list[Skipped]
) -> list[list[object]]:
    lines: list[list[object]] = []
    for result in results:
        for code in result.codes:
            message = EXCEPTIONS[code].format(
                said=result.said or "", answer=result.answer, missing=result.missing
            )
            # Where the checks set the answer aside, the model's comment argued for it.
            if code == "NEEDS_REVIEW" and result.comment and result.said is None:
                message = f"{message} {result.comment}"
            lines.append(
                [
                    result.row.sheet,
                    result.row.answer_cell,
                    result.row.question,
                    result.answer,
                    message,
                ]
            )
    for skip in skipped:
        lines.append([skip.sheet, skip.cell, skip.question, "", EXCEPTIONS[skip.code]])
    return lines


def confirmation(result: RowResult, config: JobConfig) -> dict | None:
    """What confirming a row's suggested answer writes in the requester's cells, as if the job
    had answered it: None without a suggestion, or when the cell cannot hold it."""
    if result.suggested is None:
        return None
    confirmed = replace(
        result, answer=result.suggested, said=None, suggested=None, missing="", codes=[]
    )
    written = written_value(confirmed, config)
    if written is None:
        return None
    confirmed.written = written
    row = result.row
    return {
        "answer": result.suggested,
        "written": written,
        "comment": comment_text(confirmed, config) if row.comment_cell else None,
        "evidence": evidence_text(confirmed, config) if row.evidence_cell else None,
    }


def confirm_operations(
    answers: list[dict], sheets: dict[str, str], confirmed_by: str = "a person"
) -> list[dict]:
    """The edits that confirm reported answers' suggestions: each one written as the job would
    have written it, and its lines on the added sheets saying so. `answers` are a run report's,
    each with its `confirm` and `lines`."""
    answer_at = _column(ANSWER_COLUMNS, "Answer")
    written_at = _column(ANSWER_COLUMNS, "Written in the cell")
    listed_at = _column(EXCEPTION_COLUMNS, "Answer")
    why_at = _column(EXCEPTION_COLUMNS, "Why a person should look")
    ops: list[dict] = []
    for answer in answers:
        confirm, lines, sheet = answer["confirm"], answer["lines"], answer["sheet"]
        ops.append(_set(sheet, answer["cell"], confirm["written"]))
        for cell, text in (
            (answer.get("comment_cell"), confirm.get("comment")),
            (answer.get("evidence_cell"), confirm.get("evidence")),
        ):
            if cell and text:
                ops.append(_set(sheet, cell, text))
        first, last = lines["answers"]
        for row in range(first, last + 1):
            ops.append(_set(sheets["answers"], f"{answer_at}{row}", confirm["answer"]))
            ops.append(
                _set(sheets["answers"], f"{written_at}{row}", confirm["written"])
            )
        if lines.get("exceptions"):
            first, last = lines["exceptions"]
            for row in range(first, last + 1):
                ops.append(
                    _set(sheets["exceptions"], f"{listed_at}{row}", confirm["answer"])
                )
                ops.append(
                    _set(
                        sheets["exceptions"],
                        f"{why_at}{row}",
                        f"Confirmed by {confirmed_by}: {confirm['answer']}.",
                    )
                )
    return ops


def _column(columns: tuple[str, ...], title: str) -> str:
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[columns.index(title)]


def sheet_lines(results: list[RowResult]) -> list[dict[str, list[int] | None]]:
    """Where each result's lines sit on the answers and exceptions sheets: the first and last
    row, counted from 1 with the header as row 1. Laid out as `operations` lays them."""
    found = []
    answers, exceptions = 2, 2
    for result in results:
        written = len(_answer_lines(result))
        listed = len(result.codes)
        found.append(
            {
                "answers": [answers, answers + written - 1],
                "exceptions": [exceptions, exceptions + listed - 1] if listed else None,
            }
        )
        answers += written
        exceptions += listed
    return found


def _answer_lines(result: RowResult) -> list[list[object]]:
    """One line per quote, so each source can be filtered and checked; one line without any."""
    row = result.row
    head = [
        row.sheet,
        row.answer_cell,
        row.question,
        result.answer,
        result.written or "",
        result.confidence,
    ]
    if not result.cited:
        return [[*head, "", "", None, "", result.comment]]
    return [
        [*head, c.source, c.section, c.line, c.quote, result.comment]
        for c in result.cited
    ]


def _set(sheet: str, cell: str, value: str) -> dict:
    return {"op": "set_cell", "sheet": sheet, "cell": cell, "value": value}


def _free_name(name: str, taken: list[str]) -> str:
    folded = {t.casefold() for t in taken}
    candidate, number = name, 2
    while candidate.casefold() in folded:
        suffix = f" ({number})"
        candidate = f"{name[: 31 - len(suffix)]}{suffix}"
        number += 1
    taken.append(candidate)
    return candidate
