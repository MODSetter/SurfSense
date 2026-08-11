"""Structural checks over DOCX OOXML bytes."""

from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from .base import StructuralCheckResult

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
REQUIRED_PARTS = frozenset({"[Content_Types].xml", "_rels/.rels", "word/document.xml"})
MIN_MARGIN_TWIPS = 720
MAX_MARGIN_TWIPS = 2880
MAX_ZIP_ENTRIES = 10_000
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
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
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            entry_names = [entry.filename for entry in entries]
            names = set(entry_names)
            if len(entries) > MAX_ZIP_ENTRIES:
                return StructuralCheckResult(
                    (f"DOCX contains more than {MAX_ZIP_ENTRIES} ZIP entries",)
                )
            if len(names) != len(entry_names):
                return StructuralCheckResult(("DOCX contains duplicate OOXML parts",))
            missing = sorted(REQUIRED_PARTS - names)
            if missing:
                return StructuralCheckResult(
                    (f"DOCX is missing required parts: {', '.join(missing)}",)
                )
            if any(entry.flag_bits & 1 for entry in entries):
                return StructuralCheckResult(("DOCX contains encrypted ZIP entries",))
            if sum(entry.file_size for entry in entries) > MAX_UNCOMPRESSED_BYTES:
                return StructuralCheckResult(
                    (
                        "DOCX uncompressed content exceeds "
                        f"{MAX_UNCOMPRESSED_BYTES} bytes",
                    )
                )
            document = archive.getinfo("word/document.xml")
            if document.file_size > MAX_DOCUMENT_XML_BYTES:
                return StructuralCheckResult(
                    (f"DOCX document XML exceeds {MAX_DOCUMENT_XML_BYTES} bytes",)
                )
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (BadZipFile, ElementTree.ParseError, OSError, RuntimeError):
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
        if "•" in paragraph_text and paragraph.find(f"{W}pPr/{W}numPr") is None:
            findings.append("paragraph uses a literal bullet instead of numbering")

    if _toc_present(root):
        notes.append(
            "The document contains a TOC field; page numbers populate when Word "
            "opens and updates fields."
        )

    return StructuralCheckResult(tuple(findings), notes=tuple(notes))
