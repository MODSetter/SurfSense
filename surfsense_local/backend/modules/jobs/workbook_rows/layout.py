"""Where a requester's workbook asks its questions: on each visible sheet, the header row naming
a question and an answer column, or failing that a column of dropdowns beside a column of text.

Rows a write must leave alone (hidden, locked, already answered) are kept as skipped, so the
exceptions list can say why.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from modules.artifacts.revised_copies.engines.excel_inspection import (
    SheetFacts,
    WorkbookFacts,
)
from modules.artifacts.revised_copies.engines.excel_refs import cell_name, parse_range
from modules.jobs.workbook_rows.config import LayoutWords

# Shorter text in the question column is a label, not a question.
MIN_QUESTION_CHARS = 8
# A column of questions averages longer than this; IDs and titles do not.
MIN_AVERAGE_QUESTION = 20
# How a question asking for prose starts, when it has no question mark.
_ASKS_FOR_PROSE = re.compile(
    r"^(describe|provide|list|explain|outline|detail|summari[sz]e|identify|state|specify|please)\b",
    re.IGNORECASE,
)
# Rows looked at to judge a column's text and dropdowns.
SAMPLE_ROWS = 60
# Dropdown rules sometimes cover whole columns; past this row nothing is asked.
_LAST_ROW_SLACK = 1


@dataclass(frozen=True)
class QuestionRow:
    sheet: str
    row: int
    question: str
    question_cell: str
    answer_cell: str
    comment_cell: str | None
    evidence_cell: str | None
    context: str  # what else the row and its section say, for the model
    allowed: (
        tuple[str, ...] | None
    )  # the answer cell's dropdown values; None for free text


@dataclass(frozen=True)
class Skipped:
    sheet: str
    row: int
    cell: str
    question: str
    code: str  # ROW_HIDDEN, ANSWER_LOCKED or ALREADY_ANSWERED


@dataclass(frozen=True)
class QuestionTable:
    sheet: str
    header_row: int
    question_column: int
    answer_column: int
    comment_column: int | None
    evidence_column: int | None
    context_columns: tuple[int, ...]
    found_by: str  # "headers" or "dropdowns"


@dataclass
class Layout:
    tables: list[QuestionTable] = field(default_factory=list)
    rows: list[QuestionRow] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)


def find_questions(facts: WorkbookFacts, words: LayoutWords) -> Layout:
    layout = Layout()
    for sheet in facts.sheets:
        if sheet.state != "visible" or sheet.name.casefold() in words.skip_sheets:
            continue
        # A hidden column, such as a scoring helper's, is not one the requester reads or fills.
        texts = {
            c: t for c, t in sheet.texts().items() if c[0] not in sheet.hidden_columns
        }
        if not texts:
            continue
        table = _by_headers(sheet, texts, words) or _by_dropdowns(sheet, texts, words)
        if table is None:
            continue
        layout.tables.append(table)
        _rows(sheet, texts, table, words, layout)
    return layout


def _norm(text: str) -> str:
    text = re.sub(r"\(.*?\)", " ", text.casefold())
    text = re.sub(r"[^\w/&+# -]+", " ", text)
    return " ".join(text.split())


def _matches(header: str, candidates: tuple[str, ...]) -> int:
    """How well a header names one of the words: 3 exact, 2 at an end, 1 inside a short header, 0 not."""
    name = _norm(header)
    best = 0
    for word in candidates:
        if name == word:
            return 3
        if name.startswith(f"{word} ") or name.endswith(f" {word}"):
            best = max(best, 2)
        elif len(name.split()) <= 6 and f" {word} " in f" {name} ":
            best = max(best, 1)
    return best


def _by_headers(
    sheet: SheetFacts, texts: dict[tuple[int, int], str], words: LayoutWords
) -> QuestionTable | None:
    rows = sorted({row for _, row in texts if row <= words.header_rows})
    for row in rows:
        headers = {col: text for (col, r), text in texts.items() if r == row}
        questions = [c for c, t in headers.items() if _matches(t, words.question)]
        answers = [c for c, t in headers.items() if _matches(t, words.answer)]
        if not questions or not answers:
            continue
        question = max(
            questions,
            key=lambda c: (
                _average_length(texts, c, row),
                _matches(headers[c], words.question),
            ),
        )
        # A section title such as "Required Questions" names no column of questions.
        if _average_length(texts, question, row) < MIN_AVERAGE_QUESTION:
            continue
        answers = [c for c in answers if c != question]
        if not answers:
            continue
        answer = max(
            answers,
            key=lambda c: (
                _dropdown_rows(sheet, c, row) > 0,
                _matches(headers[c], words.answer),
                -c,
            ),
        )
        taken = {question, answer}
        comment = _best(headers, words.comment, taken)
        evidence = _best(headers, words.evidence, taken | {comment})
        context = tuple(
            c
            for c, t in sorted(headers.items())
            if c not in taken | {comment, evidence} and _matches(t, words.context)
        )
        return QuestionTable(
            sheet.name, row, question, answer, comment, evidence, context, "headers"
        )
    return None


def _by_dropdowns(
    sheet: SheetFacts, texts: dict[tuple[int, int], str], words: LayoutWords
) -> QuestionTable | None:
    """A column of dropdowns is the answers; the question is the longest text to its left.

    Tables that repeat a short header over each section (HECVAT's "Answer |
    Additional information") still name the comment column there.
    """
    covered: dict[int, set[int]] = {}
    last_row = max(row for _, row in texts) + _LAST_ROW_SLACK
    for rule in sheet.dropdowns:
        for ref in rule.areas:
            area = parse_range(ref)
            if area is None:
                continue
            (left, top), (right, bottom) = area
            for column in range(left, right + 1):
                if column in sheet.hidden_columns:
                    continue
                covered.setdefault(column, set()).update(
                    range(top, min(bottom, last_row) + 1)
                )
    candidates = [(len(rows), col) for col, rows in covered.items() if len(rows) >= 3]
    if not candidates:
        return None
    _, answer = max(candidates)
    rows = sorted(covered[answer])
    sample = rows[:SAMPLE_ROWS]
    lengths = {
        col: sum(len(texts.get((col, r), "")) for r in sample)
        for col in {c for c, _ in texts}
        if col < answer
    }
    if not lengths:
        return None
    question = max(lengths, key=lambda c: (lengths[c], -abs(c - answer)))
    if lengths[question] < MIN_QUESTION_CHARS * len(sample) / 2:
        return None
    headers = _header_above(texts, answer, rows[0])
    comment = _best(headers, words.comment, {question, answer})
    evidence = _best(headers, words.evidence, {question, answer, comment})
    # A short code left of the question, such as HECVAT's DOCU-01, names the row.
    ids = tuple(
        col
        for col in range(1, question)
        if any(texts.get((col, r)) for r in sample)
        and all(len(texts.get((col, r), "")) <= 20 for r in sample)
    )
    return QuestionTable(
        sheet.name,
        max(rows[0] - 1, 0),
        question,
        answer,
        comment,
        evidence,
        ids,
        "dropdowns",
    )


def _header_above(
    texts: dict[tuple[int, int], str], answer: int, first_row: int
) -> dict[int, str]:
    """The nearest row above the answers that labels the answer column, as {column: header}."""
    for row in range(first_row - 1, max(first_row - 12, 0), -1):
        if texts.get((answer, row)):
            return {col: text for (col, r), text in texts.items() if r == row}
    return {}


def _rows(
    sheet: SheetFacts,
    texts: dict[tuple[int, int], str],
    table: QuestionTable,
    words: LayoutWords,
    layout: Layout,
) -> None:
    last_row = max(row for _, row in texts)
    data_rows = range(table.header_row + 1, last_row + 1)
    with_dropdown = [
        r for r in data_rows if sheet.dropdown_at(cell_name(table.answer_column, r))
    ]
    # Most answer cells carry a dropdown: a row without one is a section heading.
    dropdown_table = len(with_dropdown) >= 3
    section = ""
    headers = {
        col: texts.get((col, table.header_row), "") for col in table.context_columns
    }
    for row in data_rows:
        question = (texts.get((table.question_column, row)) or "").strip()
        answer_ref = cell_name(table.answer_column, row)
        dropdown = sheet.dropdown_at(answer_ref)
        if (
            len(question) < MIN_QUESTION_CHARS
            or _matches(question, words.question) == 3
        ):
            continue
        if (
            dropdown_table
            and dropdown is None
            and not _asks(question, sheet, answer_ref, words)
        ):
            section = question
            continue
        question_ref = cell_name(table.question_column, row)
        if row in sheet.hidden_rows:
            layout.skipped.append(
                Skipped(sheet.name, row, answer_ref, question, "ROW_HIDDEN")
            )
            continue
        merge = sheet.merge_of((table.answer_column, row))
        if merge is not None and merge[0] != (table.answer_column, row):
            continue
        if sheet.locked(answer_ref):
            layout.skipped.append(
                Skipped(sheet.name, row, answer_ref, question, "ANSWER_LOCKED")
            )
            continue
        if not _empty(sheet, answer_ref, words):
            layout.skipped.append(
                Skipped(sheet.name, row, answer_ref, question, "ALREADY_ANSWERED")
            )
            continue
        context = [
            f"{headers[col]}: {text}" if headers[col] else text
            for col in table.context_columns
            if (text := _merged_text(sheet, texts, col, row))
        ]
        if section:
            context.insert(0, f"Section: {section}")
        layout.rows.append(
            QuestionRow(
                sheet=sheet.name,
                row=row,
                question=question,
                question_cell=question_ref,
                answer_cell=answer_ref,
                comment_cell=_writable(sheet, table.comment_column, row, words),
                evidence_cell=_writable(sheet, table.evidence_column, row, words),
                context="; ".join(context),
                allowed=dropdown.values if dropdown is not None else None,
            )
        )


def _merged_text(
    sheet: SheetFacts, texts: dict[tuple[int, int], str], column: int, row: int
) -> str:
    """A cell's text, or its merge's: a control's title and specification are often one cell
    merged down all of its question rows, and only the first row holds the text."""
    text = texts.get((column, row))
    if text:
        return text
    merge = sheet.merge_of((column, row))
    return texts.get(merge[0], "") if merge is not None else ""


def _writable(
    sheet: SheetFacts, column: int | None, row: int, words: LayoutWords
) -> str | None:
    if column is None:
        return None
    ref = cell_name(column, row)
    if sheet.locked(ref) or not _empty(sheet, ref, words):
        return None
    # The engine refuses a write inside a merge anywhere but its first cell.
    merge = sheet.merge_of((column, row))
    if merge is not None and merge[0] != (column, row):
        return None
    return ref


def _asks(
    question: str, sheet: SheetFacts, answer_ref: str, words: LayoutWords
) -> bool:
    """A row without a dropdown in a table of dropdowns: a free-text question, or a heading.

    A question ends in a question mark (critical ones carry a trailing "*"), asks for
    prose, or waits on the requester's placeholder; a heading does none of these.
    """
    content = sheet.content(answer_ref)
    if content.kind == "text" and _empty(sheet, answer_ref, words):
        return True
    if content.kind != "empty":
        return False
    return question.rstrip(" *").endswith("?") or bool(_ASKS_FOR_PROSE.match(question))


def _empty(sheet: SheetFacts, ref: str, words: LayoutWords) -> bool:
    """Blank, or holding only the requester's placeholder text."""
    content = sheet.content(ref)
    if content.kind == "empty":
        return True
    if content.kind != "text":
        return False
    return str(content.value).strip().rstrip(".").casefold() in {
        p.rstrip(".") for p in words.placeholders
    }


def _best(
    headers: dict[int, str], candidates: tuple[str, ...], taken: set
) -> int | None:
    scored = [
        (_matches(t, candidates), -c, c) for c, t in headers.items() if c not in taken
    ]
    scored = [s for s in scored if s[0] > 0]
    return max(scored)[2] if scored else None


def _average_length(
    texts: dict[tuple[int, int], str], column: int, header_row: int
) -> float:
    lengths = [
        len(texts[(column, r)])
        for r in range(header_row + 1, header_row + 1 + SAMPLE_ROWS)
        if (column, r) in texts
    ]
    return sum(lengths) / len(lengths) if lengths else 0.0


def _dropdown_rows(sheet: SheetFacts, column: int, header_row: int) -> int:
    return sum(
        1
        for r in range(header_row + 1, header_row + 1 + SAMPLE_ROWS)
        if sheet.dropdown_at(cell_name(column, r)) is not None
    )
