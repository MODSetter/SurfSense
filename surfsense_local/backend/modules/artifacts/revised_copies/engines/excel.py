"""Edits a copy of an Excel workbook: cell values and formulas, written into the
sheet XML so charts, shapes, pivots and macros keep their bytes.

openpyxl never saves here: its round trip drops shapes and images it does not model.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from modules.artifacts.revised_copies.engines.excel_refs import parse_cell, parse_range
from modules.artifacts.revised_copies.engines.excel_sheet import (
    MAX_FORMULA,
    MAX_TEXT,
    Content,
    content_from,
    parsable_formula,
    valid_number,
)
from modules.artifacts.revised_copies.engines.excel_workbook import Workbook
from modules.artifacts.revised_copies.engines.package import open_package
from modules.artifacts.revised_copies.engines.report import (
    Notice,
    OpOutcome,
    Report,
    applied,
    bad_operation,
    nothing_changed,
    op_name,
    refused,
    skip_others,
    unsupported,
)

FORMAT = "xlsx"
OPERATIONS = ("set_cell", "set_range")
_OTHER_FORMATS = (
    "replace_text",
    "insert_paragraphs",
    "delete_paragraphs",
    "add_comment",
    "delete_slide",
    "duplicate_slide",
)
_SCALARS = (str, int, float, bool, type(None))


class _RefusedError(Exception):
    def __init__(self, outcome: OpOutcome):
        self.outcome = outcome


def apply(
    original: Path,
    operations: list[dict[str, Any]],
    out: Path,
    *,
    partial: bool = False,
    **_: Any,
) -> Report:
    input_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    package = open_package(original)
    book = Workbook(package)
    outcomes: list[OpOutcome] = []
    formulas_written = 0
    formula_cells_changed = False
    values_changed = False

    for index, operation in enumerate(operations):
        try:
            for sheet, coord, content in _resolve(book, index, operation):
                before = sheet.content(coord)
                if sheet.write(coord, content):
                    if content.kind == "formula":
                        formulas_written += 1
                    else:
                        values_changed = True
                    if (before.kind == "formula") != (content.kind == "formula"):
                        formula_cells_changed = True
            outcomes.append(applied(index, op_name(operation)))
        except _RefusedError as refusal:
            outcomes.append(refusal.outcome)
            if not partial:
                return _unsaved(skip_others(operations, refusal.outcome), (), input_sha)

    edited = book.edited()
    if not edited:
        return _unsaved(tuple(outcomes), (nothing_changed(),), input_sha)
    for part, sheet in edited:
        sheet.grow_dimension()
        package.set_xml(part, sheet.root)
    book.recalculate_on_open()
    if formula_cells_changed:
        book.drop_calc_chain()
    notices = []
    stale = formulas_written + (
        book.formula_count() - formulas_written if values_changed else 0
    )
    if stale:
        notices.append(
            Notice(
                "FORMULAS_NOT_RECALCULATED",
                {"count": stale},
                f"{stale} formula cells show no up-to-date value until the workbook is opened in "
                "Excel or LibreOffice, which recalculate it on opening.",
            )
        )
    package.save(out)
    output_sha = hashlib.sha256(out.read_bytes()).hexdigest()
    if output_sha == input_sha:
        out.unlink()
        return _unsaved(tuple(outcomes), (nothing_changed(),), input_sha)
    return Report(True, tuple(outcomes), tuple(notices), input_sha, output_sha)


def _unsaved(
    outcomes: tuple[OpOutcome, ...], notices: tuple[Notice, ...], input_sha: str
) -> Report:
    return Report(False, outcomes, notices, input_sha, None)


def _resolve(book: Workbook, index: int, operation: object):
    """The writes one operation asks for, after every check passes; nothing is written before."""
    op = op_name(operation)
    if not isinstance(operation, dict) or op == "?":
        raise _RefusedError(
            bad_operation(
                index, op, "op", "each operation is an object with an op name."
            )
        )
    if op in _OTHER_FORMATS:
        raise _RefusedError(unsupported(index, op, FORMAT))
    if op not in OPERATIONS:
        raise _RefusedError(
            bad_operation(index, op, "op", f"use one of {', '.join(OPERATIONS)}.")
        )
    sheet_name = operation.get("sheet")
    if not isinstance(sheet_name, str) or not sheet_name:
        raise _RefusedError(
            bad_operation(index, op, "sheet", "name the sheet, as on its tab.")
        )

    if op == "set_cell":
        ref = operation.get("cell")
        if not isinstance(ref, str) or not ref:
            raise _RefusedError(
                bad_operation(index, op, "cell", "give one cell such as B7.")
            )
        content = _cell_content(index, op, operation)
        sheet = _sheet(book, index, op, sheet_name)
        coord = parse_cell(ref)
        if coord is None:
            raise _RefusedError(
                refused(
                    index,
                    op,
                    "BAD_CELL",
                    {"cell": ref},
                    f"{ref} is not a cell such as B7.",
                )
            )
        _check(sheet, index, op, coord, content)
        return [(sheet, coord, content)]

    area_ref = operation.get("range")
    if not isinstance(area_ref, str) or not area_ref:
        raise _RefusedError(
            bad_operation(index, op, "range", "give a range such as A2:C4.")
        )
    rows = operation.get("values")
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        raise _RefusedError(
            bad_operation(
                index, op, "values", "send a list of rows, each a list of values."
            )
        )
    for row in rows:
        for value in row:
            _check_value(index, op, value)
    sheet = _sheet(book, index, op, sheet_name)
    area = parse_range(area_ref)
    if area is None:
        raise _RefusedError(
            refused(
                index,
                op,
                "BAD_RANGE",
                {"range": area_ref},
                f"{area_ref} is not a range such as A2:C4.",
            )
        )
    (left, top), (right, bottom) = area
    height, width = bottom - top + 1, right - left + 1
    if len(rows) != height or any(len(row) != width for row in rows):
        raise _RefusedError(
            refused(
                index,
                op,
                "RANGE_SHAPE_MISMATCH",
                {"rows": height, "columns": width},
                f"{area_ref} is {height} rows of {width} values; send exactly that shape.",
            )
        )
    writes = []
    for row_offset, row in enumerate(rows):
        for column_offset, value in enumerate(row):
            coord = (left + column_offset, top + row_offset)
            content = content_from(value)
            if content.kind == "empty" and sheet.merged_away(coord):
                continue
            _check(sheet, index, op, coord, content)
            writes.append((sheet, coord, content))
    return writes


def _cell_content(index: int, op: str, operation: dict) -> Content:
    has_value, has_formula = "value" in operation, "formula" in operation
    if has_value and has_formula:
        raise _RefusedError(
            bad_operation(index, op, "formula", "send value or formula, not both.")
        )
    if not has_value and not has_formula:
        raise _RefusedError(
            bad_operation(
                index, op, "value", "send a value, or a formula such as =SUM(B2:B6)."
            )
        )
    if has_formula:
        formula = operation["formula"]
        body = (
            formula.strip().removeprefix("=").strip()
            if isinstance(formula, str)
            else ""
        )
        if (
            not body
            or body.startswith("{")
            or len(body) > MAX_FORMULA
            or not parsable_formula(body)
        ):
            raise _RefusedError(
                bad_operation(
                    index,
                    op,
                    "formula",
                    "a formula such as =SUM(B2:B6) whose brackets and quotes pair up, "
                    "at most 8,192 characters.",
                )
            )
        return content_from(formula=body, has_formula=True)
    _check_value(index, op, operation["value"])
    return content_from(operation["value"])


def _check_value(index: int, op: str, value: object) -> None:
    if not isinstance(value, _SCALARS) or not valid_number(value):
        raise _RefusedError(
            bad_operation(
                index,
                op,
                "value" if op == "set_cell" else "values",
                "a value is text, a finite number, true, false or null.",
            )
        )
    if isinstance(value, str) and len(value) > MAX_TEXT:
        raise _RefusedError(
            bad_operation(
                index,
                op,
                "value" if op == "set_cell" else "values",
                "a cell holds at most 32,767 characters.",
            )
        )


def _sheet(book: Workbook, index: int, op: str, name: str):
    sheet = book.sheet(name)
    if sheet is None:
        names = ", ".join(book.sheets)
        raise _RefusedError(
            refused(
                index,
                op,
                "SHEET_NOT_FOUND",
                {"sheet": name, "sheets": names},
                f'No sheet is named "{name}"; the sheets are {names}.',
            )
        )
    return sheet


_MESSAGES = {
    "CELL_IN_MERGE": "{cell} is inside the merged cells {merge}; write to its first cell instead.",
    "CELL_IN_ARRAY_FORMULA": "{cell} belongs to an array formula, which this edit cannot change in part.",
    "SHARED_FORMULA_MASTER": "{cell} holds the formula other cells share; change those cells, not this one.",
    "CELL_IN_TABLE_HEADER": "{cell} is a header of table {table}; header names cannot be changed here.",
}


def _check(
    sheet, index: int, op: str, coord: tuple[int, int], content: Content
) -> None:
    problem = sheet.refusal(coord, clearing=content.kind == "empty")
    if problem is not None:
        code, values = problem
        raise _RefusedError(
            refused(index, op, code, values, _MESSAGES[code].format(**values))
        )
