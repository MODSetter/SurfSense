from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.artifacts.verification.formats.docx import (
    MAX_DOCUMENT_XML_BYTES,
    check_docx,
)
from app.artifacts.verification.formats.registry import get_format_adapter

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx(extra_body: str = "") -> bytes:
    document = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W_NS}">
  <w:body>
    <w:p><w:r><w:t>Useful document text</w:t></w:r></w:p>
    {extra_body}
    <w:sectPr>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>"""
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", document)
    return output.getvalue()


def test_clean_docx_and_registry():
    result = check_docx(_docx())
    adapter = get_format_adapter("/workspace/report.docx")

    assert result.clean
    assert adapter.name == "docx"
    assert adapter.convert_to_pdf


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            """<w:tbl>
              <w:tblPr><w:tblW w:type="pct" w:w="5000"/></w:tblPr>
              <w:tblGrid><w:gridCol w:w="3000"/></w:tblGrid>
              <w:tr><w:tc><w:tcPr><w:tcW w:type="dxa" w:w="3000"/></w:tcPr>
              <w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr>
            </w:tbl>""",
            "percentage width",
        ),
        (
            """<w:tbl><w:tblGrid><w:gridCol w:w="3000"/></w:tblGrid>
              <w:tr><w:tc><w:tcPr><w:tcW w:type="pct" w:w="5000"/></w:tcPr>
              <w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr>
            </w:tbl>""",
            "positive DXA width",
        ),
        (
            """<w:tbl><w:tblGrid><w:gridCol w:w="3000"/></w:tblGrid>
              <w:tr><w:tc><w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr>
            </w:tbl>""",
            "positive DXA width",
        ),
        (
            """<w:tbl><w:tr><w:tc><w:tcPr>
              <w:tcW w:type="dxa" w:w="3000"/></w:tcPr>
              <w:p><w:r><w:t>Cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>""",
            "missing w:tblGrid",
        ),
        (
            '<w:p><w:pPr><w:shd w:val="solid"/></w:pPr>'
            "<w:r><w:t>Shaded</w:t></w:r></w:p>",
            "solid",
        ),
        (
            "<w:p><w:r><w:t>• Literal bullet</w:t></w:r></w:p>",
            "literal bullet",
        ),
    ],
)
def test_docx_footguns_are_reported(body, message):
    result = check_docx(_docx(body))

    assert any(message in finding for finding in result.findings)


def test_numbered_bullet_is_allowed():
    result = check_docx(
        _docx(
            """<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr>
            <w:r><w:t>• Numbered bullet</w:t></w:r></w:p>"""
        )
    )

    assert not any("literal bullet" in finding for finding in result.findings)


def test_toc_is_a_non_fatal_note():
    result = check_docx(
        _docx(
            '<w:p><w:fldSimple w:instr="TOC \\o &quot;1-3&quot;"/>'
            "<w:r><w:t>Contents</w:t></w:r></w:p>"
        )
    )

    assert result.clean
    assert "populate when Word opens" in result.notes[0]


def test_docx_rejects_missing_parts():
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")

    result = check_docx(output.getvalue())

    assert "missing required parts" in result.findings[0]


def test_docx_rejects_duplicate_parts():
    output = BytesIO()
    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        ZipFile(output, "w") as archive,
    ):
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("word/document.xml", "<document/>")

    result = check_docx(output.getvalue())

    assert result.findings == ("DOCX contains duplicate OOXML parts",)


def test_docx_rejects_oversized_document_xml_before_decompression():
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document.xml", b"x" * (MAX_DOCUMENT_XML_BYTES + 1))

    result = check_docx(output.getvalue())

    assert "document XML exceeds" in result.findings[0]
