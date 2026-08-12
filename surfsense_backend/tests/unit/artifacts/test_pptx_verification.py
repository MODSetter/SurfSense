from __future__ import annotations

from contextlib import nullcontext
from io import BytesIO
from zipfile import ZipFile

import pytest

from app.artifacts.verification.formats.pptx import check_pptx

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _presentation(slide_ids: str = '<p:sldId id="256" r:id="rId1"/>') -> str:
    return f"""<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">
      <p:sldIdLst>{slide_ids}</p:sldIdLst>
      <p:sldSz cx="12192000" cy="6858000"/>
    </p:presentation>"""


def _shape(
    *,
    kind: str = "sp",
    x: int = 0,
    y: int = 0,
    width: int = 1_000_000,
    height: int = 1_000_000,
    extra: str = "",
) -> str:
    return f"""<p:{kind}>
      <p:nvSpPr/>
      <p:spPr><a:xfrm><a:off x="{x}" y="{y}"/>
        <a:ext cx="{width}" cy="{height}"/></a:xfrm>{extra}</p:spPr>
    </p:{kind}>"""


def _slide(shape: str | None = None, *, attributes: str = "", extra: str = "") -> str:
    return f"""<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" {attributes}>
      <p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/>
        {shape if shape is not None else _shape()}
      </p:spTree></p:cSld>{extra}
    </p:sld>"""


def _parts() -> dict[str, str]:
    return {
        "[Content_Types].xml": "<Types/>",
        "_rels/.rels": f'<Relationships xmlns="{REL_NS}"/>',
        "ppt/presentation.xml": _presentation(),
        "ppt/_rels/presentation.xml.rels": f"""<Relationships xmlns="{REL_NS}">
          <Relationship Id="rId1" Type="{R_NS}/slide" Target="slides/slide1.xml"/>
        </Relationships>""",
        "ppt/slides/slide1.xml": _slide(),
    }


def _package(parts: dict[str, str], *, duplicate: str | None = None) -> bytes:
    output = BytesIO()
    with (
        pytest.warns(UserWarning, match="Duplicate name")
        if duplicate
        else nullcontext(),
        ZipFile(output, "w") as archive,
    ):
        for name, value in parts.items():
            archive.writestr(name, value)
        if duplicate:
            archive.writestr(duplicate, parts[duplicate])
    return output.getvalue()


def _mark_first_entry_encrypted(data: bytes) -> bytes:
    encrypted = bytearray(data)
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        offset = encrypted.find(signature)
        assert offset >= 0
        flags = int.from_bytes(
            encrypted[offset + flag_offset : offset + flag_offset + 2], "little"
        )
        encrypted[offset + flag_offset : offset + flag_offset + 2] = (
            flags | 1
        ).to_bytes(2, "little")
    return bytes(encrypted)


def test_clean_pptx_reports_exact_slide_count():
    result = check_pptx(_package(_parts()))

    assert result.clean
    assert result.page_count == 1


def test_pptx_rejects_missing_duplicate_and_encrypted_parts():
    missing = _parts()
    del missing["ppt/presentation.xml"]

    assert "missing required parts" in check_pptx(_package(missing)).findings[0]
    assert check_pptx(
        _package(_parts(), duplicate="ppt/presentation.xml")
    ).findings == ("PPTX contains duplicate OOXML parts",)
    assert (
        "encrypted ZIP entries"
        in check_pptx(_mark_first_entry_encrypted(_package(_parts()))).findings[0]
    )


def test_pptx_rejects_zero_slides():
    parts = _parts()
    parts["ppt/presentation.xml"] = _presentation("")

    result = check_pptx(_package(parts))

    assert result.findings == ("PPTX contains no slides",)
    assert result.page_count == 0


def test_pptx_rejects_dangling_slide_relationship():
    parts = _parts()
    parts["ppt/_rels/presentation.xml.rels"] = f'<Relationships xmlns="{REL_NS}"/>'

    result = check_pptx(_package(parts))

    assert "missing slide part" in result.findings[0]
    assert result.page_count == 1


@pytest.mark.parametrize(
    ("slide", "message"),
    [
        (_slide(attributes='show="0"'), "is hidden"),
        (_slide(shape=""), "no drawable shapes"),
        (_slide(_shape(x=13_000_000)), "entirely off the canvas"),
        (_slide(_shape(width=0)), "non-positive extent"),
        (
            _slide(_shape(kind="cxnSp", width=0, height=0)),
            "non-positive extent",
        ),
        (
            _slide(extra='<a:srcRect l="60000" r="40000"/>'),
            "crop that removes the entire image",
        ),
        (_slide(extra='<a:srcRect l="invalid"/>'), "invalid picture crop"),
    ],
)
def test_pptx_reports_slide_structure_defects(slide, message):
    parts = _parts()
    parts["ppt/slides/slide1.xml"] = slide

    result = check_pptx(_package(parts))

    assert any(message in finding for finding in result.findings)


@pytest.mark.parametrize(
    "shape",
    [
        _shape(kind="cxnSp", width=0),
        _shape(kind="cxnSp", height=0),
        _shape(kind="cxnSp", y=0, height=0),
        _shape(kind="cxnSp", x=12_192_000, width=0),
    ],
)
def test_pptx_allows_axis_aligned_connectors_on_canvas_boundaries(shape):
    parts = _parts()
    parts["ppt/slides/slide1.xml"] = _slide(shape)

    assert check_pptx(_package(parts)).clean


def test_pptx_allows_legal_extended_picture_crops():
    parts = _parts()
    parts["ppt/slides/slide1.xml"] = _slide(extra='<a:srcRect l="-10000" r="105000"/>')

    assert check_pptx(_package(parts)).clean


def test_pptx_rejects_dangling_embedded_media():
    parts = _parts()
    picture = """<p:pic><p:nvPicPr/><p:blipFill>
      <a:blip r:embed="rId2"/>
    </p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/>
      <a:ext cx="1000000" cy="1000000"/></a:xfrm></p:spPr></p:pic>"""
    parts["ppt/slides/slide1.xml"] = _slide(picture)
    parts["ppt/slides/_rels/slide1.xml.rels"] = f'<Relationships xmlns="{REL_NS}"/>'

    result = check_pptx(_package(parts))

    assert "missing embedded media" in result.findings[0]
