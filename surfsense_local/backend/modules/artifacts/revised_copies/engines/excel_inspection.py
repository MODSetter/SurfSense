"""What a workbook's own rules say about writing into it: each sheet's visibility,
protection, dropdowns, merged cells and hidden rows, read as the engine reads them."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.artifacts.revised_copies.engines.excel_dropdowns import Dropdown
from modules.artifacts.revised_copies.engines.excel_protection import sheet_protected
from modules.artifacts.revised_copies.engines.excel_refs import (
    in_range,
    parse_cell,
    range_name,
)
from modules.artifacts.revised_copies.engines.excel_sheet import (
    Content,
    Sheet,
    shown_value,
)
from modules.artifacts.revised_copies.engines.excel_workbook import Workbook
from modules.artifacts.revised_copies.engines.package import open_package


@dataclass
class SheetFacts:
    name: str
    state: str  # visible, hidden or veryHidden
    protected: bool
    dropdowns: list[Dropdown]
    merged: list[str]
    hidden_rows: frozenset[int]
    hidden_columns: frozenset[int]
    _book: Workbook
    _sheet: Sheet

    def dropdown_at(self, ref: str) -> Dropdown | None:
        coord = parse_cell(ref)
        return None if coord is None else self._book.dropdown_at(self._sheet, coord)

    def locked(self, ref: str) -> bool:
        coord = parse_cell(ref)
        return coord is not None and self._book.locked(self._sheet, coord)

    def content(self, ref: str) -> Content:
        coord = parse_cell(ref)
        return self._sheet.content(coord) if coord is not None else Content("empty")

    def texts(self) -> dict[tuple[int, int], str]:
        """Every cell as it reads on screen: its value, or a formula's last result.

        HECVAT, for one, shows each question through a formula over a hidden sheet.
        """
        found = {}
        for coord in self._sheet.cells():
            content = self._sheet.content(coord)
            if content.kind == "formula":
                content = self._sheet.cached_result(coord)
            if (
                content.kind in ("text", "number", "boolean")
                and shown_value(content).strip()
            ):
                found[coord] = shown_value(content)
        return found

    def merge_of(
        self, coord: tuple[int, int]
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        return next(
            (area for area in self._sheet.merges if in_range(coord, area)), None
        )


@dataclass
class WorkbookFacts:
    sheets: list[SheetFacts]

    def sheet(self, name: str) -> SheetFacts | None:
        return next(
            (s for s in self.sheets if s.name.casefold() == name.casefold()), None
        )


def inspect_workbook(path: Path) -> WorkbookFacts:
    """Every sheet's facts, in tab order; reads only, so the file is left as it was."""
    book = Workbook(open_package(path))
    facts = []
    for name in book.sheets:
        sheet = book.sheet(name)
        assert sheet is not None  # listed by the workbook itself
        facts.append(
            SheetFacts(
                name=name,
                state=book.states.get(name, "visible"),
                protected=sheet_protected(sheet.root),
                dropdowns=book.dropdowns(sheet),
                merged=[range_name(*area) for area in sheet.merges],
                hidden_rows=sheet.hidden_rows(),
                hidden_columns=sheet.hidden_columns(),
                _book=book,
                _sheet=sheet,
            )
        )
    return WorkbookFacts(facts)
