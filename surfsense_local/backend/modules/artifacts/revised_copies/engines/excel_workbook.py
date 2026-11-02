"""The workbook around the sheets: which part is which sheet, its tables, its
shared strings, and the calculation settings an edit has to reset."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from urllib.parse import unquote

from lxml import etree

from modules.artifacts.revised_copies.engines.excel_dropdowns import (
    Dropdown,
    dropdowns,
    split_reference,
)
from modules.artifacts.revised_copies.engines.excel_new_sheet import new_sheet
from modules.artifacts.revised_copies.engines.excel_protection import (
    sheet_protected,
    unlocked_styles,
)
from modules.artifacts.revised_copies.engines.excel_refs import parse_range
from modules.artifacts.revised_copies.engines.excel_sheet import (
    Coord,
    Sheet,
    Table,
    shown_value,
)
from modules.artifacts.revised_copies.engines.package import (
    Package,
    PackageRefusedError,
)

# A list longer than this is no dropdown anyone picks from; it is left unchecked.
_LIST_CELLS = 10_000
_WORKSHEET_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)

_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_STRICT_REL_ID = "{http://purl.oclc.org/ooxml/officeDocument/relationships}id"

# CT_Workbook's children in schema order (ECMA-376 Part 1, 18.2.27), for placing calcPr.
_AFTER_CALC_PR = (
    "oleSize",
    "customWorkbookViews",
    "pivotCaches",
    "smartTagPr",
    "smartTagTypes",
    "webPublishing",
    "fileRecoveryPr",
    "webPublishObjects",
    "extLst",
)


@dataclass(frozen=True)
class Relationship:
    id: str
    type: str
    target: str
    external: bool


def relationships(package: Package, part: str) -> list[Relationship]:
    folder = posixpath.dirname(part)
    found = []
    for rel in package.relationships(part):
        external = rel.get("TargetMode") == "External"
        target = rel.get("Target", "")
        if not external:
            target = unquote(target.split("#", 1)[0])
            target = posixpath.normpath(
                target.lstrip("/")
                if target.startswith("/")
                else posixpath.join(folder, target)
            )
        found.append(
            Relationship(rel.get("Id", ""), rel.get("Type", ""), target, external)
        )
    return found


class Workbook:
    def __init__(self, package: Package):
        self.package = package
        main = next(
            (
                r
                for r in relationships(package, "")
                if r.type.endswith("/officeDocument") and not r.external
            ),
            None,
        )
        kind = ""
        if main is not None and main.target in package.names:
            kind = package.content_type(main.target) or ""
        if "spreadsheetml" not in kind and "ms-excel" not in kind:
            raise PackageRefusedError(
                "NOT_A_WORKBOOK",
                {},
                "The file has no workbook part, so it is not an Excel workbook.",
            )
        self.part = main.target
        self.root = package.xml(self.part)
        self.ns = etree.QName(self.root).namespace
        self._rels = relationships(package, self.part)
        by_id = {r.id: r for r in self._rels}
        self.sheets: dict[str, str] = {}
        for sheet in self.root.iter(f"{{{self.ns}}}sheet"):
            rel = by_id.get(sheet.get(_REL_ID) or sheet.get(_STRICT_REL_ID) or "")
            if rel and rel.type.endswith("/worksheet") and rel.target in package.names:
                self.sheets[sheet.get("name", "")] = rel.target
        # visible, hidden or veryHidden, by sheet name.
        self.states: dict[str, str] = {
            sheet.get("name", ""): sheet.get("state", "visible")
            for sheet in self.root.iter(f"{{{self.ns}}}sheet")
            if sheet.get("name", "") in self.sheets
        }
        self._open: dict[str, Sheet] = {}
        self._shared: list[str] | None = None
        self._dropdowns: dict[str, list[Dropdown]] = {}
        self._unlocked: frozenset[int] | None = None

    def sheet(self, name: str) -> Sheet | None:
        """Excel treats sheet names case-insensitively, and so does this."""
        part = self._part_named(name)
        if part is None:
            return None
        if part not in self._open:
            self._open[part] = Sheet(
                self.package.xml(part), self._tables(part), self._shared_text
            )
        return self._open[part]

    def name_of(self, sheet: Sheet) -> str:
        part = next(p for p, s in self._open.items() if s is sheet)
        return next(n for n, p in self.sheets.items() if p == part)

    def dropdowns(self, sheet: Sheet) -> list[Dropdown]:
        """The sheet's list rules, read from the sheet as it was opened."""
        part = next(p for p, s in self._open.items() if s is sheet)
        if part not in self._dropdowns:
            name = self.name_of(sheet)
            self._dropdowns[part] = dropdowns(
                sheet.root, lambda reference: self.list_values(reference, name)
            )
        return self._dropdowns[part]

    def dropdown_at(self, sheet: Sheet, coord: Coord) -> Dropdown | None:
        """The rule a cell takes; where rules overlap Excel applies the first."""
        return next((d for d in self.dropdowns(sheet) if d.covers(coord)), None)

    def locked(self, sheet: Sheet, coord: Coord) -> bool:
        """Whether Excel refuses typing into the cell: its sheet is protected and its style locks it."""
        if not sheet_protected(sheet.root):
            return False
        if self._unlocked is None:
            self._unlocked = unlocked_styles(self._styles())
        return sheet.style_of(coord) not in self._unlocked

    def list_values(self, reference: str, on_sheet: str) -> tuple[str, ...] | None:
        """The texts a list's cells hold, from a range or a defined name; None when unreadable."""
        sheet_name, cells = split_reference(self._defined(reference, on_sheet))
        sheet = self.sheet(sheet_name or on_sheet)
        if sheet is None:
            return None
        cells = cells.replace("$", "")
        if re.fullmatch(r"[A-Za-z]{1,3}:[A-Za-z]{1,3}", cells):
            first, last = cells.split(":")
            if first.upper() != last.upper():
                return None
            column = parse_range(f"{first}1")[0][0]
            coords = [(column, row) for row in sheet.column_rows(column)]
        else:
            area = parse_range(cells)
            if area is None:
                return None
            (left, top), (right, bottom) = area
            if (right - left + 1) * (bottom - top + 1) > _LIST_CELLS:
                return None
            coords = [
                (column, row)
                for row in range(top, bottom + 1)
                for column in range(left, right + 1)
            ]
        texts = []
        for coord in coords:
            content = sheet.content(coord)
            if content.kind in ("text", "number", "boolean"):
                texts.append(shown_value(content))
        return tuple(texts)

    def _defined(self, reference: str, on_sheet: str) -> str:
        """A defined name's reference, the sheet's own scope first; anything else as it is."""
        names = self.root.find(f"{{{self.ns}}}definedNames")
        if names is None or not re.fullmatch(r"[A-Za-z_\\][\w.\\]*", reference):
            return reference
        position = list(self.sheets).index(on_sheet) if on_sheet in self.sheets else -1
        matches = [
            n
            for n in names.findall(f"{{{self.ns}}}definedName")
            if n.get("name", "").casefold() == reference.casefold()
        ]
        scoped = [n for n in matches if n.get("localSheetId") == str(position)]
        chosen = (scoped or [n for n in matches if n.get("localSheetId") is None])[:1]
        return (chosen[0].text or "").strip().removeprefix("=") if chosen else reference

    def add_sheet(self, name: str, rows: list[list[object]]) -> None:
        """A new last sheet holding `rows`; its name was checked with `name_problem`."""
        existing = next(iter(self.sheets.values()))
        rel = next(r for r in self._rels if r.target == existing)
        number = 1
        while f"xl/worksheets/sheet{number}.xml" in self.package.names:
            number += 1
        part = f"xl/worksheets/sheet{number}.xml"
        rid = self.package.add_part(
            part,
            new_sheet(self.ns, rows),
            self.package.content_type(existing) or _WORKSHEET_TYPE,
            self.part,
            rel.type,
        )
        sheets = self.root.find(f"{{{self.ns}}}sheets")
        listed = list(sheets.iter(f"{{{self.ns}}}sheet"))
        entry = etree.SubElement(sheets, f"{{{self.ns}}}sheet")
        entry.set("name", name)
        entry.set(
            "sheetId",
            str(max((int(s.get("sheetId", "0")) for s in listed), default=0) + 1),
        )
        id_attribute = (
            _STRICT_REL_ID
            if any(_STRICT_REL_ID in s.attrib for s in listed)
            else _REL_ID
        )
        entry.set(id_attribute, rid)
        self.package.set_xml(self.part, self.root)
        self._rels = relationships(self.package, self.part)
        self.sheets[name] = part
        self.states[name] = "visible"

    def _part_named(self, name: str) -> str | None:
        part = self.sheets.get(name)
        if part is None:
            folded = [
                p for n, p in self.sheets.items() if n.casefold() == name.casefold()
            ]
            part = folded[0] if len(folded) == 1 else None
        return part

    def _styles(self) -> etree._Element | None:
        part = next(
            (
                r.target
                for r in self._rels
                if r.type.endswith("/styles")
                and not r.external
                and r.target in self.package.names
            ),
            None,
        )
        return self.package.xml(part) if part else None

    def edited(self) -> list[tuple[str, Sheet]]:
        return [(part, sheet) for part, sheet in self._open.items() if sheet.written]

    def formula_count(self) -> int:
        return sum(
            (
                self._open[part]
                if part in self._open
                else Sheet(self.package.xml(part), [], self._shared_text)
            ).formula_count()
            for part in self.sheets.values()
        )

    def recalculate_on_open(self) -> None:
        calc = self.root.find(f"{{{self.ns}}}calcPr")
        if calc is None:
            calc = etree.Element(f"{{{self.ns}}}calcPr")
            later = [c for c in self.root if etree.QName(c).localname in _AFTER_CALC_PR]
            if later:
                later[0].addprevious(calc)
            else:
                self.root.append(calc)
        calc.set("fullCalcOnLoad", "1")
        self.package.set_xml(self.part, self.root)

    def drop_calc_chain(self) -> None:
        """Excel rebuilds the chain; a stale one naming cells without formulas makes it repair the file."""
        for rel in self._rels:
            if (
                rel.type.endswith("/calcChain")
                and not rel.external
                and rel.target in self.package.names
            ):
                self.package.remove(rel.target)

    def _tables(self, sheet_part: str) -> list[Table]:
        tables = []
        for rel in relationships(self.package, sheet_part):
            if not rel.type.endswith("/table") or rel.target not in self.package.names:
                continue
            root = self.package.xml(rel.target)
            area = parse_range(root.get("ref", ""))
            header = None
            if area is not None and root.get("headerRowCount", "1") != "0":
                header = (area[0], (area[1][0], area[0][1]))
            tables.append(
                Table(root.get("displayName") or root.get("name") or "", header)
            )
        return tables

    def _shared_text(self, index: int) -> str | None:
        if self._shared is None:
            strings = next(
                (
                    r.target
                    for r in self._rels
                    if r.type.endswith("/sharedStrings") and not r.external
                ),
                None,
            )
            self._shared = []
            if strings and strings in self.package.names:
                root = self.package.xml(strings)
                ns = etree.QName(root).namespace
                for item in root.findall(f"{{{ns}}}si"):
                    self._shared.append(
                        "".join(
                            t.text or ""
                            for t in item.iter(f"{{{ns}}}t")
                            if etree.QName(t.getparent()).localname != "rPh"
                        )
                    )
        return self._shared[index] if 0 <= index < len(self._shared) else None
