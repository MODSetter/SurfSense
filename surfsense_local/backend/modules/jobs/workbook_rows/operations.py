"""The revise engine's operations for a filled questionnaire: each answer in its own cell, a comment
and a source where the requester left room for them, then a sheet of every answer's sources (a
line per quote) and a sheet of the exceptions, after the requester's own."""

from __future__ import annotations

from string import Template

from modules.jobs.workbook_rows.config import JobConfig
from modules.jobs.workbook_rows.decide import EXCEPTIONS, RowResult, template_fields
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
