"""The workbook around the sheets: which part is which sheet, its tables, its
shared strings, and the calculation settings an edit has to reset."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from urllib.parse import unquote

from lxml import etree

from modules.artifacts.revised_copies.engines.excel_refs import parse_range
from modules.artifacts.revised_copies.engines.excel_sheet import Sheet, Table
from modules.artifacts.revised_copies.engines.package import (
    Package,
    PackageRefusedError,
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
        self._open: dict[str, Sheet] = {}
        self._shared: list[str] | None = None

    def sheet(self, name: str) -> Sheet | None:
        """Excel treats sheet names case-insensitively, and so does this."""
        part = self.sheets.get(name)
        if part is None:
            folded = [
                p for n, p in self.sheets.items() if n.casefold() == name.casefold()
            ]
            part = folded[0] if len(folded) == 1 else None
        if part is None:
            return None
        if part not in self._open:
            self._open[part] = Sheet(
                self.package.xml(part), self._tables(part), self._shared_text
            )
        return self._open[part]

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
