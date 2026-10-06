"""What an Excel workbook a script wrote holds, as a summary the model checks instead of pages.

A workbook has no pages to preview, so the agent reads this: each sheet's
used range and first rows, and the formulas it found.
"""

import re
import zipfile
from io import BytesIO
from typing import Any

import openpyxl
from openpyxl.worksheet.formula import ArrayFormula

from worker.studio.script_document.extracted_text import UnreadableDocumentError

# Enough rows and columns to see a sheet's shape and header; the rest is counted.
ROWS = 10
COLUMNS = 8
CELL_CHARS = 40
SHEETS = 10
FORMULAS = 20
FORMULA_CHARS = 200
# The whole summary stays one readable tool result, whatever the script wrote.
SUMMARY_CHARS = 6000
# Cells read across the workbook. A row is read padded to its sheet's last
# column, so one cell written far out would otherwise mean billions.
CELLS_READ = 200_000

_CHART_PART = re.compile(r"xl/charts/chart\d+\.xml")
_PLAIN_SHEET_NAME = re.compile(r"\w+")


def workbook_summary(data: bytes) -> str:
    """The workbook's sheets and charts counted, each sheet summarised, then its formulas."""
    try:
        # Read-only streams the rows: a script may write a very long sheet.
        book = openpyxl.load_workbook(BytesIO(data), read_only=True)
        charts = _chart_count(data)
    # A file that is not a workbook fails as a zip, key or value error.
    except Exception as error:
        raise UnreadableDocumentError from error
    try:
        # Chartsheets hold no cells; their charts are counted with the rest.
        sheets = list(book.worksheets)
        blocks = [_counts(len(sheets), charts)]
        formulas: list[str] = []
        cells_left = CELLS_READ
        for sheet in sheets[:SHEETS]:
            block, read = _sheet_block(sheet, formulas, cells_left)
            blocks.append(block)
            cells_left -= read
        if len(sheets) > SHEETS:
            blocks.append(f"({len(sheets) - SHEETS} more sheets)")
        if formulas:
            blocks.append("\n".join(["Formulas:", *_formula_lines(formulas)]))
    finally:
        book.close()
    summary = "\n\n".join(blocks)
    if len(summary) > SUMMARY_CHARS:
        return f"{summary[:SUMMARY_CHARS]}… (summary cut)"
    return summary


def _counts(sheets: int, charts: int) -> str:
    counted = f"A workbook of {_plural(sheets, 'sheet')}"
    if charts:
        counted += f" and {_plural(charts, 'chart')}"
    return f"{counted}."


def _sheet_block(sheet: Any, formulas: list[str], cells_left: int) -> tuple[str, int]:
    """The sheet's name and used range, its first rows as a table, and how many
    cells were read, about `cells_left` at most; its formulas go to `formulas`."""
    rows: list[str] = []
    more = 0
    read = 0
    rows_read = 0
    cut = False
    for row in sheet.iter_rows():
        if read >= cells_left:
            cut = True
            break
        read += len(row)
        rows_read += 1
        values = [_value(cell.value) for cell in row]
        for cell, value in zip(row, values, strict=True):
            if _is_formula(value):
                formulas.append(f"{_reference(sheet.title)}{cell.coordinate}: {value}")
        if all(value is None for value in values):
            continue
        if len(rows) < ROWS:
            rows.append(_row_line(values))
        else:
            more += 1
    if not rows and not cut:
        return f'Sheet "{sheet.title}": empty', read
    lines = [f'Sheet "{sheet.title}": {_used_range(sheet, read_whole=not cut)}', *rows]
    if more:
        lines.append(f"({more} more rows)")
    if cut:
        lines.append(
            f"(rows after row {rows_read} not read)" if rows_read else "(not read)"
        )
    return "\n".join(lines), read


def _value(value: Any) -> Any:
    """A cell's value; an array formula comes as an object holding its text."""
    return value.text if isinstance(value, ArrayFormula) else value


def _used_range(sheet: Any, *, read_whole: bool) -> str:
    """The range the file records; measured only when the sheet was read whole,
    since measuring reads every row again."""
    try:
        dimension = sheet.calculate_dimension(force=read_whole)
    except ValueError:
        return "size not recorded"
    first, _, last = dimension.partition(":")
    return first if last in ("", first) else f"{first}:{last}"


def _row_line(values: list[Any]) -> str:
    while values and values[-1] is None:
        values = values[:-1]
    shown = [_cell_text(value) for value in values[:COLUMNS]]
    if len(values) > COLUMNS:
        shown.append(f"… {len(values) - COLUMNS} more columns")
    return " | ".join(shown)


def _cell_text(value: Any) -> str:
    text = "" if value is None else " ".join(str(value).split())
    return text if len(text) <= CELL_CHARS else f"{text[:CELL_CHARS]}…"


def _formula_lines(formulas: list[str]) -> list[str]:
    lines = [
        f"- {formula if len(formula) <= FORMULA_CHARS else formula[:FORMULA_CHARS] + '…'}"
        for formula in formulas[:FORMULAS]
    ]
    if len(formulas) > FORMULAS:
        lines.append(f"- (and {len(formulas) - FORMULAS} more)")
    return lines


def _is_formula(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("=")


def _reference(title: str) -> str:
    """How a formula names the sheet: quoted when the name has spaces or punctuation."""
    if _PLAIN_SHEET_NAME.fullmatch(title):
        return f"{title}!"
    return "'{}'!".format(title.replace("'", "''"))


def _chart_count(data: bytes) -> int:
    with zipfile.ZipFile(BytesIO(data)) as package:
        return sum(1 for name in package.namelist() if _CHART_PART.fullmatch(name))


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"
