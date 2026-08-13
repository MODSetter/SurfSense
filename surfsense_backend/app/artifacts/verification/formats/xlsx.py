"""Structural checks over XLSX OOXML bytes (no recalc, no vision)."""

from __future__ import annotations

from xml.etree import ElementTree

from .base import StructuralCheckResult
from .ooxml import OoxmlDefect, open_ooxml

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
MAIN = f"{{{MAIN_NS}}}"
REL = f"{{{PKG_REL_NS}}}"
R_ID = f"{{{OFFICE_REL_NS}}}id"

REQUIRED_PARTS = frozenset(
    {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
)
MAX_WORKBOOK_XML_BYTES = 2 * 1024 * 1024
MAX_CELLS = 100_000
EXCEL_ERRORS = frozenset(
    {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#NULL!", "#NUM!", "#N/A"}
)


def _sheet_targets(archive) -> list[str]:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    target_by_id = {
        rel.get("Id"): rel.get("Target")
        for rel in rels.iter(f"{REL}Relationship")
        if rel.get("Id") and rel.get("Target")
    }
    targets: list[str] = []
    for sheet in workbook.iter(f"{MAIN}sheet"):
        rel_id = sheet.get(R_ID)
        target = target_by_id.get(rel_id or "")
        if not target:
            continue
        if target.startswith("/"):
            targets.append(target.lstrip("/"))
        else:
            targets.append(f"xl/{target.lstrip('./')}")
    return targets


def check_xlsx(data: bytes) -> StructuralCheckResult:
    findings: list[str] = []
    if not data:
        return StructuralCheckResult(("XLSX is empty",))

    try:
        with open_ooxml(
            data,
            format_name="XLSX",
            required_parts=REQUIRED_PARTS,
            part_limits={"xl/workbook.xml": MAX_WORKBOOK_XML_BYTES},
        ) as archive:
            sheet_paths = _sheet_targets(archive)
            if not sheet_paths:
                return StructuralCheckResult(("XLSX workbook has no worksheets",))

            cell_count = 0
            non_empty = 0
            for sheet_path in sheet_paths:
                try:
                    sheet_xml = archive.read(sheet_path)
                except KeyError:
                    findings.append(f"XLSX is missing worksheet part {sheet_path}")
                    continue
                try:
                    root = ElementTree.fromstring(sheet_xml)
                except ElementTree.ParseError:
                    findings.append(f"XLSX worksheet {sheet_path} is not valid XML")
                    continue
                for cell in root.iter(f"{MAIN}c"):
                    cell_count += 1
                    if cell_count > MAX_CELLS:
                        return StructuralCheckResult(
                            (
                                f"XLSX has more than {MAX_CELLS} cells; "
                                "download-only size for verification",
                            )
                        )
                    formula = cell.find(f"{MAIN}f")
                    value = cell.find(f"{MAIN}v")
                    inline = cell.find(f"{MAIN}is")
                    has_value = value is not None and (value.text or "").strip() != ""
                    has_inline = inline is not None
                    if formula is not None:
                        if not has_value:
                            findings.append(
                                "formula cell is missing a cached result value"
                            )
                            continue
                        cached = (value.text or "").strip()
                        if cell.get("t") == "e" or cached in EXCEL_ERRORS:
                            findings.append(
                                f"formula cell cached result is an Excel error ({cached})"
                            )
                        non_empty += 1
                    elif has_value or has_inline:
                        non_empty += 1
    except OoxmlDefect as exc:
        return StructuralCheckResult((str(exc),))
    except ElementTree.ParseError:
        return StructuralCheckResult(("XLSX is not valid OOXML",))

    if non_empty == 0 and not findings:
        findings.append("XLSX contains no non-empty cells")

    # Deduplicate while preserving order — sheet loops can repeat the same defect.
    unique: list[str] = []
    seen: set[str] = set()
    for finding in findings:
        if finding not in seen:
            seen.add(finding)
            unique.append(finding)
    return StructuralCheckResult(tuple(unique))
