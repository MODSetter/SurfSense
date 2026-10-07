"""One worksheet's XML, edited cell by cell (ECMA-376 Part 1, 18.3).

Values and formulas only: styles stay as they are, and a new cell takes its
row's or column's style the way Excel would.
"""

from __future__ import annotations

import math
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

from lxml import etree

from modules.artifacts.revised_copies.engines.excel_refs import (
    cell_name,
    column_letters,
    in_range,
    parse_cell,
    parse_range,
    range_name,
)

Coord = tuple[int, int]
Area = tuple[Coord, Coord]

# Excel's own limits (Excel specifications and limits).
MAX_TEXT = 32_767
MAX_FORMULA = 8_192

_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿\ud800-\udfff]")
_ESCAPE_LOOKALIKE = re.compile(r"_(x[0-9A-Fa-f]{4}_)")
_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


@dataclass(frozen=True)
class Content:
    """What a cell holds: kind is number, text, boolean, formula or empty."""

    kind: str
    value: object = None


EMPTY = Content("empty")


@dataclass(frozen=True)
class Table:
    name: str
    header: Area | None


class Sheet:
    def __init__(
        self,
        root: etree._Element,
        tables: list[Table],
        shared_text: Callable[[int], str | None],
    ):
        self.root = root
        self.ns = etree.QName(root).namespace
        self._tables = tables
        self._shared_text = shared_text
        self.data = self._child(root, "sheetData")
        if self.data is None:
            self.data = etree.Element(self._q("sheetData"))
            root.insert(self._sheet_data_position(), self.data)
        self._rows: dict[int, etree._Element] = {}
        self._cells: dict[Coord, etree._Element] = {}
        self._index()
        self._merges = [
            area
            for merge in root.iter(self._q("mergeCell"))
            if (area := parse_range(merge.get("ref", ""))) is not None
        ]
        self._column_styles = [
            (int(col.get("min", "0")), int(col.get("max", "0")), col.get("style"))
            for col in root.iter(self._q("col"))
            if col.get("style") not in (None, "0")
        ]
        self.written: set[Coord] = set()

    # --- reading -------------------------------------------------------------

    def refusal(self, coord: Coord, clearing: bool) -> tuple[str, dict] | None:
        name = cell_name(*coord)
        for merge in self._merges:
            if in_range(coord, merge) and coord != merge[0] and not clearing:
                return "CELL_IN_MERGE", {"cell": name, "merge": range_name(*merge)}
        for area in self._array_areas():
            if in_range(coord, area):
                return "CELL_IN_ARRAY_FORMULA", {"cell": name}
        cell = self._cells.get(coord)
        formula = self._child(cell, "f") if cell is not None else None
        if (
            formula is not None
            and formula.get("t") == "shared"
            and formula.get("ref")
            and self._has_shared_dependents(formula.get("si"), cell)
        ):
            return "SHARED_FORMULA_MASTER", {"cell": name}
        for table in self._tables:
            if table.header and in_range(coord, table.header):
                return "CELL_IN_TABLE_HEADER", {"cell": name, "table": table.name}
        return None

    def merged_away(self, coord: Coord) -> bool:
        return any(
            in_range(coord, merge) and coord != merge[0] for merge in self._merges
        )

    def content(self, coord: Coord) -> Content:
        cell = self._cells.get(coord)
        if cell is None:
            return EMPTY
        formula = self._child(cell, "f")
        if formula is not None:
            return Content("formula", formula.text or "")
        kind = cell.get("t", "n")
        if kind == "inlineStr":
            inline = self._child(cell, "is")
            return (
                Content("text", _unescape(self._rich_text(inline)))
                if inline is not None
                else EMPTY
            )
        raw = self._child(cell, "v")
        if raw is None or raw.text is None:
            return EMPTY
        if kind == "s":
            text = (
                self._shared_text(int(raw.text)) if raw.text.strip().isdigit() else None
            )
            return (
                Content("text", _unescape(text))
                if text is not None
                else Content("unknown")
            )
        if kind == "b":
            return Content("boolean", raw.text.strip() == "1")
        if kind == "n":
            try:
                return Content("number", float(raw.text))
            except ValueError:
                return Content("unknown")
        return Content("unknown")

    def formula_count(self) -> int:
        return sum(1 for _ in self.data.iter(self._q("f")))

    # --- writing -------------------------------------------------------------

    def write(self, coord: Coord, content: Content) -> bool:
        """Whether the cell changed."""
        if _same(self.content(coord), content):
            return False
        cell = self._cells.get(coord)
        if cell is None:
            if content.kind == "empty":
                return False
            cell = self._new_cell(coord)
        for child in list(cell):
            if etree.QName(child).localname in ("f", "v", "is"):
                cell.remove(child)
        for attribute in ("t", "cm", "vm"):
            cell.attrib.pop(attribute, None)
        if content.kind == "empty":
            if cell.get("s") in (None, "0") and len(cell) == 0:
                cell.getparent().remove(cell)
                del self._cells[coord]
        elif content.kind == "text":
            cell.set("t", "inlineStr")
            inline = etree.Element(self._q("is"))
            text = etree.SubElement(inline, self._q("t"))
            text.text = _escape(str(content.value))
            if text.text != text.text.strip(" \t\n") or "\n" in text.text:
                text.set(_SPACE, "preserve")
            cell.insert(0, inline)
        elif content.kind == "formula":
            formula = etree.Element(self._q("f"))
            formula.text = str(content.value)
            cell.insert(0, formula)
        else:
            raw = etree.Element(self._q("v"))
            if content.kind == "boolean":
                cell.set("t", "b")
                raw.text = "1" if content.value else "0"
            else:
                raw.text = _number(content.value)
            cell.insert(0, raw)
        self.written.add(coord)
        return True

    def grow_dimension(self) -> None:
        dimension = self._child(self.root, "dimension")
        if dimension is None or not self.written:
            return
        area = parse_range(dimension.get("ref", ""))
        columns = [c for c, _ in self.written]
        rows = [r for _, r in self.written]
        if area is not None:
            columns += [area[0][0], area[1][0]]
            rows += [area[0][1], area[1][1]]
        dimension.set(
            "ref", range_name((min(columns), min(rows)), (max(columns), max(rows)))
        )

    # --- internals -----------------------------------------------------------

    def _q(self, name: str) -> str:
        return f"{{{self.ns}}}{name}"

    def _child(self, parent: etree._Element | None, name: str) -> etree._Element | None:
        return None if parent is None else parent.find(self._q(name))

    def _index(self) -> None:
        # Row and cell references are optional; give them explicit ones so inserts can be ordered.
        last_row = 0
        for row in self.data.findall(self._q("row")):
            number = int(row.get("r") or last_row + 1)
            row.set("r", str(number))
            last_row = number
            self._rows[number] = row
            last_column = 0
            for cell in row.findall(self._q("c")):
                coord = parse_cell(cell.get("r", "")) or (last_column + 1, number)
                cell.set("r", cell_name(*coord))
                last_column = coord[0]
                self._cells[coord] = cell

    def _new_cell(self, coord: Coord) -> etree._Element:
        column, number = coord
        row = self._rows.get(number)
        if row is None:
            row = etree.Element(self._q("row"))
            row.set("r", str(number))
            later = [r for n, r in self._rows.items() if n > number]
            if later:
                min(later, key=lambda r: int(r.get("r"))).addprevious(row)
            else:
                self.data.append(row)
            self._rows[number] = row
        row.attrib.pop("spans", None)
        cell = etree.Element(self._q("c"))
        cell.set("r", f"{column_letters(column)}{number}")
        style = self._style_for(row, column)
        if style:
            cell.set("s", style)
        following = [
            c for (col, r), c in self._cells.items() if r == number and col > column
        ]
        if following:
            min(following, key=lambda c: parse_cell(c.get("r"))[0]).addprevious(cell)
        else:
            last = row.findall(self._q("c"))
            if last:
                last[-1].addnext(cell)
            else:
                row.insert(0, cell)
        self._cells[coord] = cell
        return cell

    def _style_for(self, row: etree._Element, column: int) -> str | None:
        if row.get("customFormat") in ("1", "true") and row.get("s"):
            return row.get("s")
        return next(
            (
                style
                for low, high, style in self._column_styles
                if low <= column <= high
            ),
            None,
        )

    def _array_areas(self) -> list[Area]:
        areas = []
        for formula in self.data.iter(self._q("f")):
            if formula.get("t") in ("array", "dataTable") and formula.get("ref"):
                area = parse_range(formula.get("ref"))
                if area is not None:
                    areas.append(area)
        return areas

    def _has_shared_dependents(self, index: str | None, master: etree._Element) -> bool:
        return any(
            formula.get("t") == "shared"
            and formula.get("si") == index
            and formula.getparent() is not master
            for formula in self.data.iter(self._q("f"))
        )

    def _rich_text(self, element: etree._Element) -> str:
        # Phonetic runs (rPh) are reading aids, not the cell's text.
        return "".join(
            t.text or ""
            for t in element.iter(self._q("t"))
            if etree.QName(t.getparent()).localname != "rPh"
        )

    def _sheet_data_position(self) -> int:
        before = {"sheetPr", "dimension", "sheetViews", "sheetFormatPr", "cols"}
        return sum(1 for child in self.root if etree.QName(child).localname in before)


def content_from(
    value: object = None, formula: object = None, has_formula: bool = False
) -> Content:
    if has_formula:
        return Content("formula", str(formula).strip().removeprefix("="))
    if value is None:
        return EMPTY
    if isinstance(value, bool):
        return Content("boolean", value)
    if isinstance(value, int | float):
        return Content("number", value)
    return Content("text", value)


def valid_number(value: object) -> bool:
    """Excel stores IEEE doubles: no NaN, no infinity, no integer beyond one."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return True
    return abs(value) <= sys.float_info.max and math.isfinite(value)


_CLOSING = {")": "(", "}": "{", "]": "["}


def parsable_formula(body: str) -> bool:
    """Brackets pair up and quotes close, outside text and quoted sheet names.

    Excel repairs a sheet holding a formula it cannot parse, dropping the formula.
    """
    if _XML_INVALID.search(body):
        return False
    open_brackets: list[str] = []
    quote = ""
    for char in body:
        if quote:
            # A doubled quote escapes itself: it closes and at once reopens.
            quote = "" if char == quote else quote
        elif char in "\"'":
            quote = char
        elif char in "({[":
            open_brackets.append(char)
        elif char in _CLOSING and (
            not open_brackets or open_brackets.pop() != _CLOSING[char]
        ):
            return False
    return not quote and not open_brackets


def _same(old: Content, new: Content) -> bool:
    if old.kind != new.kind:
        return False
    if new.kind == "number":
        return float(old.value) == float(new.value)
    return old.value == new.value


def _number(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    as_float = float(value)
    return (
        str(int(as_float))
        if as_float.is_integer() and abs(as_float) < 1e15
        else repr(as_float)
    )


def _escape(text: str) -> str:
    """ST_Xstring: a literal _xHHHH_ keeps its underscore escaped, and characters
    XML 1.0 cannot carry become _xHHHH_ (ECMA-376 Part 1, 22.9.2.19)."""
    text = _ESCAPE_LOOKALIKE.sub(r"_x005F_\1", text)
    return _XML_INVALID.sub(lambda m: f"_x{ord(m.group()):04X}_", text)


def _unescape(text: str) -> str:
    return re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m.group(1), 16)), text)
