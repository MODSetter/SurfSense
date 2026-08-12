"""Structural checks over DOCX OOXML bytes."""

from __future__ import annotations

from xml.etree import ElementTree

from .base import StructuralCheckResult
from .ooxml import OoxmlDefect, open_ooxml

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
REQUIRED_PARTS = frozenset({"[Content_Types].xml", "_rels/.rels", "word/document.xml"})
MIN_MARGIN_TWIPS = 720
MAX_MARGIN_TWIPS = 2880
MAX_DOCUMENT_XML_BYTES = 10 * 1024 * 1024


def _attribute(element: ElementTree.Element, name: str) -> str | None:
    return element.get(f"{W}{name}")


def _toc_present(root: ElementTree.Element) -> bool:
    instructions = [element.text or "" for element in root.iter(f"{W}instrText")]
    instructions.extend(
        _attribute(element, "instr") or "" for element in root.iter(f"{W}fldSimple")
    )
    return any(
        instruction.strip().upper().startswith("TOC") for instruction in instructions
    )


def check_docx(data: bytes) -> StructuralCheckResult:
    findings: list[str] = []
    notes: list[str] = []
    if not data:
        return StructuralCheckResult(("DOCX is empty",))

    try:
        with open_ooxml(
            data,
            format_name="DOCX",
            required_parts=REQUIRED_PARTS,
            part_limits={"word/document.xml": MAX_DOCUMENT_XML_BYTES},
        ) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except OoxmlDefect as exc:
        return StructuralCheckResult((str(exc),))
    except ElementTree.ParseError:
        return StructuralCheckResult(("DOCX is not valid OOXML",))

    body = root.find(f"{W}body")
    text = "".join(element.text or "" for element in root.iter(f"{W}t")).strip()
    if body is None or not text:
        findings.append("DOCX body contains no text")

    sections = list(root.iter(f"{W}sectPr"))
    if not sections:
        findings.append("DOCX has no section page setup")
    for index, section in enumerate(sections, start=1):
        margins = section.find(f"{W}pgMar")
        if margins is None:
            findings.append(f"section {index} has no page margins")
            continue
        for side in ("top", "right", "bottom", "left"):
            raw = _attribute(margins, side)
            try:
                value = int(raw) if raw is not None else 0
            except ValueError:
                value = 0
            if not MIN_MARGIN_TWIPS <= value <= MAX_MARGIN_TWIPS:
                findings.append(
                    f"section {index} has an unsafe {side} margin ({raw or 'missing'} twips)"
                )

    for width in root.iter(f"{W}tblW"):
        if _attribute(width, "type") == "pct":
            findings.append("table uses percentage width; use DXA widths")
    for cell in root.iter(f"{W}tc"):
        width = cell.find(f"{W}tcPr/{W}tcW")
        if width is None:
            findings.append("table cell is missing a positive DXA width")
            continue
        width_type = _attribute(width, "type")
        raw_width = _attribute(width, "w")
        try:
            numeric_width = int(raw_width) if raw_width is not None else 0
        except ValueError:
            numeric_width = 0
        if width_type != "dxa" or numeric_width <= 0:
            findings.append("table cell is missing a positive DXA width")

    for table in root.iter(f"{W}tbl"):
        grid = table.find(f"{W}tblGrid")
        if grid is None or not list(grid.findall(f"{W}gridCol")):
            findings.append("table is missing w:tblGrid column widths")

    if any(_attribute(shading, "val") == "solid" for shading in root.iter(f"{W}shd")):
        findings.append("shading uses solid; use clear shading")

    for paragraph in root.iter(f"{W}p"):
        paragraph_text = "".join(
            element.text or "" for element in paragraph.iter(f"{W}t")
        )
        if (
            paragraph_text.lstrip().startswith("•")
            and paragraph.find(f"{W}pPr/{W}numPr") is None
        ):
            findings.append("paragraph uses a literal bullet instead of numbering")

    if _toc_present(root):
        notes.append(
            "The document contains a TOC field; page numbers populate when Word "
            "opens and updates fields."
        )

    return StructuralCheckResult(tuple(findings), notes=tuple(notes))
