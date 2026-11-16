"""A Word table as compact markdown: one line per row, no padding.

A merged cell's text appears once, in its first grid cell; the cells it spans
stay empty so the columns still line up. Docling repeats it in every one.
"""

from collections.abc import Callable, Iterator
from typing import Any

from worker.ingestion.word_markdown.ooxml_names import (
    CUSTOM_XML,
    SDT,
    SDT_CONTENT,
    TC,
    TR,
    VAL,
    w,
)

_TBL_GRID = w("tblGrid")
_GRID_COL = w("gridCol")
_TR_PR = w("trPr")
_TC_PR = w("tcPr")
_GRID_BEFORE = w("gridBefore")
_GRID_SPAN = w("gridSpan")
_DELETED_ROW = f"{_TR_PR}/{w('del')}"
_MOST_SPANNED = 64


def rows_of(table: Any) -> list[Any]:
    """The rows Word shows with tracked changes accepted: a deleted one is gone."""
    return [row for row in _wrapped(table, TR) if row.find(_DELETED_ROW) is None]


def grid_columns(table: Any) -> int:
    grid = table.find(_TBL_GRID)
    return 0 if grid is None else len(grid.findall(_GRID_COL))


def cells_of(row: Any) -> list[Any]:
    return list(_wrapped(row, TC))


def markdown_table(table: Any, cell_text: Callable[[Any], str]) -> str:
    """The table's rows, or "" when no cell has any text."""
    rows = [_row(row, cell_text) for row in rows_of(table)]
    if not any(any(row) for row in rows):
        return ""
    width = max(len(row) for row in rows)
    lines = []
    for n, row in enumerate(rows):
        cells = [cell.replace("|", "\\|") for cell in row] + [""] * (width - len(row))
        lines.append("| " + " | ".join(cells) + " |")
        if n == 0:
            lines.append("|" + "---|" * width)
    return "\n".join(lines)


def _row(row: Any, cell_text: Callable[[Any], str]) -> list[str]:
    cells = [""] * min(_number(row.find(f"{_TR_PR}/{_GRID_BEFORE}"), 0), _MOST_SPANNED)
    for cell in cells_of(row):
        properties = cell.find(_TC_PR)
        span = _number(None if properties is None else properties.find(_GRID_SPAN), 1)
        # A cell merged from the row above holds no text of its own.
        cells.append(cell_text(cell).replace("\n", " "))
        cells.extend([""] * (min(max(span, 1), _MOST_SPANNED) - 1))
    return cells


def _wrapped(parent: Any, tag: str) -> Iterator[Any]:
    """Children with the tag, also inside content controls and custom XML."""
    for child in parent.iterchildren():
        if child.tag == tag:
            yield child
        elif child.tag == SDT:
            content = child.find(SDT_CONTENT)
            if content is not None:
                yield from _wrapped(content, tag)
        elif child.tag == CUSTOM_XML:
            yield from _wrapped(child, tag)


def _number(element: Any | None, default: int) -> int:
    try:
        return int(element.get(VAL)) if element is not None else default
    except (TypeError, ValueError):
        return default
