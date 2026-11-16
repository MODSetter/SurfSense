"""A new worksheet from rows of values: header row frozen, columns sized to their text.

Built with the same cell writer as edits, so text is escaped and ordered the one way.
"""

from __future__ import annotations

from lxml import etree

from modules.artifacts.revised_copies.engines.excel_refs import range_name
from modules.artifacts.revised_copies.engines.excel_sheet import Sheet, content_from

_FORBIDDEN = set("\\/?*[]:")
MAX_NAME = 31
# Excel refuses a sheet of this name: it keeps it for tracked-change history.
_RESERVED = "history"
# Characters per column before text wraps from view; Excel's own cap is 255.
_WIDEST = 80


def name_problem(name: str, taken: list[str]) -> str | None:
    """The code Excel's own rule gives a new sheet's name, or None when it may be used."""
    if name.casefold() in (t.casefold() for t in taken):
        return "SHEET_EXISTS"
    if (
        not name.strip()
        or len(name) > MAX_NAME
        or _FORBIDDEN & set(name)
        or name.startswith("'")
        or name.endswith("'")
        or name.casefold() == _RESERVED
    ):
        return "BAD_SHEET_NAME"
    return None


def new_sheet(namespace: str, rows: list[list[object]]) -> etree._Element:
    root = etree.Element(f"{{{namespace}}}worksheet", nsmap={None: namespace})
    etree.SubElement(root, f"{{{namespace}}}sheetData")
    sheet = Sheet(root, [], lambda _: None)
    for row_number, row in enumerate(rows, start=1):
        for column, value in enumerate(row, start=1):
            sheet.write((column, row_number), content_from(value))
    _frame(root, namespace, rows)
    return root


def _frame(root: etree._Element, ns: str, rows: list[list[object]]) -> None:
    """Dimension, a frozen header row and column widths, each in schema order before sheetData."""
    width = max((len(row) for row in rows), default=0)
    if not rows or not width:
        return
    data = root.find(f"{{{ns}}}sheetData")
    dimension = etree.Element(f"{{{ns}}}dimension")
    dimension.set("ref", range_name((1, 1), (width, len(rows))))
    views = etree.Element(f"{{{ns}}}sheetViews")
    view = etree.SubElement(views, f"{{{ns}}}sheetView")
    view.set("workbookViewId", "0")
    if len(rows) > 1:
        pane = etree.SubElement(view, f"{{{ns}}}pane")
        pane.set("ySplit", "1")
        pane.set("topLeftCell", "A2")
        pane.set("activePane", "bottomLeft")
        pane.set("state", "frozen")
    cols = etree.Element(f"{{{ns}}}cols")
    for column in range(width):
        longest = max(
            (
                len(str(row[column]))
                for row in rows
                if column < len(row) and row[column] is not None
            ),
            default=8,
        )
        col = etree.SubElement(cols, f"{{{ns}}}col")
        col.set("min", str(column + 1))
        col.set("max", str(column + 1))
        col.set("width", str(min(max(longest, 8), _WIDEST) + 2))
        col.set("customWidth", "1")
    for element in (dimension, views, cols):
        data.addprevious(element)
