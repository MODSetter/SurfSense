from __future__ import annotations

from io import BytesIO
from zipfile import ZipFile

import pytest

from app.artifacts.verification import service
from app.artifacts.verification.formats.registry import XLSX_MIME, get_format_adapter
from app.artifacts.verification.formats.xlsx import MAX_CELLS, check_xlsx
from app.artifacts.verification.receipt import RECEIPT_PATH, read_receipt
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 7

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _xlsx(*, sheet_body: str, sheet_count: int = 1) -> bytes:
    sheets = "\n".join(
        f'<sheet name="Sheet{i}" sheetId="{i}" '
        f'r:id="rId{i}" xmlns:r="{OFFICE_REL_NS}"/>'
        for i in range(1, sheet_count + 1)
    )
    rels = "\n".join(
        f'<Relationship Id="rId{i}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheet_count + 1)
    )
    workbook = f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{MAIN_NS}" xmlns:r="{OFFICE_REL_NS}">
  <sheets>{sheets}</sheets>
</workbook>"""
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<Relationships xmlns="{PKG_REL_NS}">{rels}</Relationships>',
        )
        for i in range(1, sheet_count + 1):
            body = sheet_body if i == 1 else '<c r="A1"><v>1</v></c>'
            archive.writestr(
                f"xl/worksheets/sheet{i}.xml",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_NS}">
  <sheetData><row r="1">{body}</row></sheetData>
</worksheet>""",
            )
    return output.getvalue()


def test_clean_xlsx_and_registry():
    result = check_xlsx(_xlsx(sheet_body='<c r="A1"><v>10</v></c>'))
    adapter = get_format_adapter("/workspace/budget.xlsx")

    assert result.clean
    assert adapter.name == "xlsx"
    assert adapter.mime_type == XLSX_MIME
    assert not adapter.requires_visual_review
    assert not adapter.convert_to_pdf


def test_formula_with_cached_value_passes():
    result = check_xlsx(_xlsx(sheet_body='<c r="B1"><f>SUM(A1)</f><v>10</v></c>'))
    assert result.clean


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('<c r="B1"><f>SUM(A1)</f></c>', "cached result"),
        ('<c r="B1" t="e"><f>1/0</f><v>#DIV/0!</v></c>', "Excel error"),
        ("", "no non-empty cells"),
    ],
)
def test_xlsx_structural_findings(body, message):
    result = check_xlsx(_xlsx(sheet_body=body))
    assert not result.clean
    assert any(message in finding for finding in result.findings)


def test_xlsx_cell_ceiling():
    cells = "".join(f'<c r="A{i}"><v>1</v></c>' for i in range(1, MAX_CELLS + 2))
    sheet = f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="{MAIN_NS}">
  <sheetData><row r="1">{cells}</row></sheetData>
</worksheet>"""
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="{MAIN_NS}" xmlns:r="{OFFICE_REL_NS}">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f"""<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
    Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet)

    result = check_xlsx(output.getvalue())
    assert not result.clean
    assert any(str(MAX_CELLS) in finding for finding in result.findings)


async def test_verify_xlsx_structural_only_skips_render_and_vision():
    """Real adapter + real OOXML; sandbox is the only stand-in (boundary)."""
    path = "/workspace/budget.xlsx"
    data = _xlsx(sheet_body='<c r="A1"><v>10</v></c>')
    session = FakeSandboxSession({path: data})

    result = await service.verify_artifact(
        session,
        path,
        workspace_id=WORKSPACE_ID,
        vision_llm=object(),
        secret_key=SECRET,
    )
    receipt = await read_receipt(session, SECRET, workspace_id=WORKSPACE_ID)

    assert result.verified
    assert result.preview_path is None
    assert result.findings == ()
    assert receipt.format == "xlsx"
    assert receipt.visual == "not_required"
    assert receipt.preview_path is None
    assert receipt.preview_sha256 is None
    assert receipt.primary_sha256
    # Early exit must not touch LibreOffice / rasterize / vision.
    assert session.commands == []


async def test_verify_xlsx_structural_failure_issues_no_receipt():
    path = "/workspace/budget.xlsx"
    session = FakeSandboxSession(
        {path: _xlsx(sheet_body='<c r="B1"><f>SUM(A1)</f></c>')}
    )

    result = await service.verify_artifact(
        session,
        path,
        workspace_id=WORKSPACE_ID,
        vision_llm=None,
        secret_key=SECRET,
    )

    assert not result.verified
    assert any("cached result" in finding for finding in result.findings)
    assert session.files[RECEIPT_PATH] == b""
    assert session.commands == []
