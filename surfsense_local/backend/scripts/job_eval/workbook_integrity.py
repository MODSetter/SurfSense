"""Whether a filled workbook is still the requester's: same sheets in the same order, the same
dropdowns and protection, and no cell changed outside the ones the job may write."""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import openpyxl
from lxml import etree

from modules.artifacts.revised_copies.engines.excel_inspection import inspect_workbook
from modules.artifacts.revised_copies.engines.excel_refs import cell_name

_KEPT = ("dataValidations", "sheetProtection", "mergeCells", "conditionalFormatting")
_X14 = "{http://schemas.microsoft.com/office/spreadsheetml/2009/9/main}dataValidations"


def integrity_problems(
    original: Path, filled: Path, writable: set[tuple[str, str]]
) -> list[str]:
    """Each way `filled` departs from `original` beyond the cells in `writable` (sheet, cell)."""
    problems: list[str] = []
    before, after = inspect_workbook(original), inspect_workbook(filled)
    names_before = [s.name for s in before.sheets]
    names_after = [s.name for s in after.sheets]
    if names_after[: len(names_before)] != names_before:
        problems.append(f"sheet order changed: {names_before} became {names_after}")
    for sheet in before.sheets:
        kept = after.sheet(sheet.name)
        if kept is None:
            problems.append(f"sheet {sheet.name} is gone")
            continue
        if kept.state != sheet.state:
            problems.append(
                f"sheet {sheet.name} went from {sheet.state} to {kept.state}"
            )
        old, new = sheet.texts(), kept.texts()
        for coord in set(old) | set(new):
            if (
                old.get(coord) != new.get(coord)
                and (sheet.name, cell_name(*coord)) not in writable
            ):
                problems.append(
                    f"{sheet.name}!{cell_name(*coord)} changed outside the answers"
                )
    old_parts, new_parts = _sheet_rules(original), _sheet_rules(filled)
    for part, rules in old_parts.items():
        if new_parts.get(part) != rules:
            problems.append(f"{part}: its dropdowns, protection or merges changed")
    try:
        openpyxl.load_workbook(
            io.BytesIO(filled.read_bytes()), keep_vba=filled.suffix == ".xlsm"
        )
    except Exception as unreadable:  # openpyxl raises many kinds on a broken file
        problems.append(f"openpyxl cannot open it: {unreadable}")
    for name in _binary_parts(original):
        if _read(original, name) != _read(filled, name):
            problems.append(f"{name} changed")
    return problems


def _sheet_rules(path: Path) -> dict[str, list[bytes]]:
    rules: dict[str, list[bytes]] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if not re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name):
                continue
            root = etree.fromstring(archive.read(name))
            ns = etree.QName(root).namespace
            found = [
                etree.tostring(element, method="c14n")
                for tag in _KEPT
                for element in root.iter(f"{{{ns}}}{tag}")
            ]
            found += [etree.tostring(e, method="c14n") for e in root.iter(_X14)]
            rules[name] = found
    return rules


def _binary_parts(path: Path) -> list[str]:
    """Macros, media, charts and drawings: parts no answer should touch."""
    with zipfile.ZipFile(path) as archive:
        return [
            n
            for n in archive.namelist()
            if n.endswith(".bin")
            or n.startswith(("xl/media/", "xl/charts/", "xl/drawings/", "xl/pivot"))
        ]


def _read(path: Path, name: str) -> bytes | None:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name) if name in archive.namelist() else None
