"""A workbook's formula cells given the values LibreOffice computed, at the XML level.

Only `<v>` and `t` of formula cells change, and `fullCalcOnLoad` is set, so the
file stays the one the script wrote: LibreOffice's own re-written workbook is
never delivered (04, section 7).
"""

import posixpath
import zipfile
from dataclasses import dataclass
from io import BytesIO

from lxml import etree
from openpyxl.utils.cell import get_column_letter, range_boundaries

from modules.office_support import CellValue, WorkbookValues

_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_WORKBOOK = "xl/workbook.xml"
_WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"
# calcPr comes after these in CT_Workbook's sequence.
_BEFORE_CALC = ("sheets", "functionGroups", "externalReferences", "definedNames")


@dataclass(frozen=True)
class CachedValues:
    """The workbook with values written, how many formulas got one, and how many were left blank."""

    data: bytes
    written: int
    left_blank: int


def count_formulas(data: bytes) -> int:
    """How many formula cells the workbook's worksheets hold."""
    with zipfile.ZipFile(BytesIO(data)) as package:
        return sum(
            len(_formula_cells(etree.fromstring(package.read(part))))
            for part in _sheet_parts(package).values()
        )


def with_cached_values(data: bytes, values: WorkbookValues) -> CachedValues:
    """Write each formula's value from `values`; a formula with none is left blank, never stale."""
    written = left_blank = 0
    replaced: dict[str, bytes] = {}
    with zipfile.ZipFile(BytesIO(data)) as package:
        for sheet, part in _sheet_parts(package).items():
            root = etree.fromstring(package.read(part))
            computed = values.get(sheet, {})
            for cell in _formula_cells(root):
                value = computed.get(cell.get("r", ""))
                _set_value(cell, value)
                if value is None:
                    left_blank += 1
                else:
                    written += 1
            # Counted with their array formula, but each caches its own value.
            for cell in _array_filled_cells(root):
                _set_value(cell, computed.get(cell.get("r", "")))
            replaced[part] = _xml(root)
        replaced[_WORKBOOK] = _xml(
            _full_calc_on_load(etree.fromstring(package.read(_WORKBOOK)))
        )
        out = BytesIO()
        with zipfile.ZipFile(out, "w") as rewritten:
            for item in package.infolist():
                body = replaced.get(item.filename)
                rewritten.writestr(
                    item, body if body is not None else package.read(item)
                )
    return CachedValues(out.getvalue(), written, left_blank)


def _sheet_parts(package: zipfile.ZipFile) -> dict[str, str]:
    """Each worksheet's name and its part, as the workbook lists them."""
    workbook = etree.fromstring(package.read(_WORKBOOK))
    rels = etree.fromstring(package.read(_WORKBOOK_RELS))
    targets = {
        rel.get("Id"): rel.get("Target", "")
        for rel in rels.iter(f"{{{_PACKAGE_REL}}}Relationship")
        if rel.get("Type", "").endswith("/worksheet")
    }
    parts: dict[str, str] = {}
    for sheet in workbook.iter(f"{{{_MAIN}}}sheet"):
        target = targets.get(sheet.get(f"{{{_REL}}}id"))
        if target is None:
            continue  # a chartsheet holds no cells
        part = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join("xl", target))
        )
        if part in package.namelist():
            parts[sheet.get("name", "")] = part
    return parts


def _formula_cells(root: etree._Element) -> list[etree._Element]:
    return [
        cell
        for cell in root.iter(f"{{{_MAIN}}}c")
        if cell.find(f"{{{_MAIN}}}f") is not None
    ]


def _array_filled_cells(root: etree._Element) -> list[etree._Element]:
    """The cells an array formula fills besides its own, which hold a value and no formula."""
    covered = {
        ref
        for formula in root.iter(f"{{{_MAIN}}}f")
        if formula.get("t") == "array" and formula.get("ref")
        for ref in _cells_in(formula.get("ref"))
    }
    return [
        cell
        for cell in root.iter(f"{{{_MAIN}}}c")
        if cell.get("r") in covered and cell.find(f"{{{_MAIN}}}f") is None
    ]


def _cells_in(ref: str) -> list[str]:
    first_column, first_row, last_column, last_row = range_boundaries(ref)
    return [
        f"{get_column_letter(column)}{row}"
        for row in range(first_row, last_row + 1)
        for column in range(first_column, last_column + 1)
    ]


def _set_value(cell: etree._Element, value: CellValue | None) -> None:
    for old in cell.findall(f"{{{_MAIN}}}v") + cell.findall(f"{{{_MAIN}}}is"):
        cell.remove(old)
    if value is None:
        cell.attrib.pop("t", None)
        return
    if isinstance(value, bool):
        kind, text = "b", "1" if value else "0"
    elif isinstance(value, int | float):
        kind, text = None, repr(value) if isinstance(value, float) else str(value)
    else:
        kind, text = "str", value
    if kind is None:
        cell.attrib.pop("t", None)
    else:
        cell.set("t", kind)
    v = etree.Element(f"{{{_MAIN}}}v")
    v.text = text
    formula = cell.find(f"{{{_MAIN}}}f")
    if formula is None:
        cell.insert(0, v)
    else:
        formula.addnext(v)


def _full_calc_on_load(workbook: etree._Element) -> etree._Element:
    """Excel recalculates on open whatever was cached."""
    calc = workbook.find(f"{{{_MAIN}}}calcPr")
    if calc is None:
        calc = etree.Element(f"{{{_MAIN}}}calcPr")
        anchor = None
        for name in _BEFORE_CALC:
            found = workbook.find(f"{{{_MAIN}}}{name}")
            if found is not None:
                anchor = found
        if anchor is None:
            workbook.append(calc)
        else:
            anchor.addnext(calc)
    calc.set("fullCalcOnLoad", "1")
    return workbook


def _xml(root: etree._Element) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
