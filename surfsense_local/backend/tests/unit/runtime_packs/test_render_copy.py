"""The copy LibreOffice opens points at no other file and runs no linking field."""

import io
import zipfile
from pathlib import Path

import pytest

from modules.runtime_packs.office.soffice.render_copy import neutralize_external

pytestmark = pytest.mark.unit

RELS = (
    '<?xml version="1.0"?><Relationships xmlns="x">'
    '<Relationship Id="rId1" Type="t/styles" Target="styles.xml"/>'
    '<Relationship Id="rId2" Type="t/image" Target="file:///C:/secret/a.png" TargetMode="External"/>'
    "<Relationship Id='rId3' TargetMode='External' Type='t/hyperlink' Target='https://example.org/'/>"
    "</Relationships>"
)
DOCUMENT = (
    '<w:document xmlns:w="w"><w:body>'
    '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    '<w:r><w:instrText xml:space="preserve"> INCLUDETEXT </w:instrText></w:r>'
    '<w:r><w:instrText>"C:\\\\secret.docx"</w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>last result</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
    "<w:r><w:instrText> PAGE </w:instrText></w:r>"
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
    "<w:r><w:t>1</w:t></w:r>"
    '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    '<w:p><w:fldSimple w:instr=" INCLUDEPICTURE &quot;C:\\\\x.png&quot; ">'
    "<w:r><w:t>picture</w:t></w:r></w:fldSimple></w:p>"
    "</w:body></w:document>"
)
EXTERNAL_LINK = (
    '<externalLink xmlns="x"><ddeLink ddeService="cmd" ddeTopic="/c calc">'
    "</ddeLink></externalLink>"
)
STYLES = b"<styles>untouched \xc3\xa9</styles>"


def _docx(path: Path) -> Path:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/_rels/document.xml.rels", RELS)
        archive.writestr("word/document.xml", DOCUMENT)
        archive.writestr("word/styles.xml", STYLES)
        archive.writestr("xl/externalLinks/externalLink1.xml", EXTERNAL_LINK)
    path.write_bytes(buffer.getvalue())
    return path


def _part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode()


def test_external_targets_point_nowhere_and_internal_ones_stay(tmp_path: Path) -> None:
    """Both quote styles; an internal part keeps its target."""
    copy = _docx(tmp_path / "copy.docx")
    neutralize_external(copy)
    rels = _part(copy, "word/_rels/document.xml.rels")
    assert 'Target="styles.xml"' in rels
    assert "secret" not in rels
    assert "example.org" not in rels
    assert rels.count("about:invalid") == 2


def test_linking_fields_lose_their_instruction_and_keep_their_result(
    tmp_path: Path,
) -> None:
    """INCLUDETEXT across two runs and INCLUDEPICTURE go; PAGE stays."""
    copy = _docx(tmp_path / "copy.docx")
    neutralize_external(copy)
    document = _part(copy, "word/document.xml")
    assert "INCLUDETEXT" not in document
    assert "secret" not in document
    assert "INCLUDEPICTURE" not in document
    assert "last result" in document
    assert "picture" in document
    assert " PAGE " in document


def test_dde_links_lose_their_program(tmp_path: Path) -> None:
    """A workbook's DDE link cannot start a program."""
    copy = _docx(tmp_path / "copy.docx")
    neutralize_external(copy)
    link = _part(copy, "xl/externalLinks/externalLink1.xml")
    assert 'ddeService=""' in link
    assert "calc" not in link


def test_parts_with_nothing_to_change_keep_their_bytes(tmp_path: Path) -> None:
    """Untouched parts are not re-encoded."""
    copy = _docx(tmp_path / "copy.docx")
    neutralize_external(copy)
    with zipfile.ZipFile(copy) as archive:
        assert archive.read("word/styles.xml") == STYLES


def test_a_file_that_is_not_a_zip_is_left_alone(tmp_path: Path) -> None:
    """A legacy .doc has no XML to change."""
    legacy = tmp_path / "old.doc"
    legacy.write_bytes(b"\xd0\xcf\x11\xe0 legacy")
    neutralize_external(legacy)
    assert legacy.read_bytes() == b"\xd0\xcf\x11\xe0 legacy"


def _package(path: Path, parts: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return path


def test_any_namespace_prefix_is_neutralized(tmp_path: Path) -> None:
    """LibreOffice reads elements by namespace, so a prefix other than w: is no way round."""
    copy = _package(
        tmp_path / "copy.docx",
        {
            "word/_rels/document.xml.rels": (
                b'<pr:Relationships xmlns:pr="x"><pr:Relationship Id="rId2" '
                b'Type="t/image" Target="file:///C:/secret/a.png" TargetMode="External"/>'
                b"</pr:Relationships>"
            ),
            "word/document.xml": (
                b'<x:document xmlns:x="w"><x:body><x:p>'
                b'<x:r><x:fldChar x:fldCharType="begin"/></x:r>'
                b'<x:r><x:instrText> INCLUDETEXT "C:\\secret.docx" </x:instrText></x:r>'
                b'<x:r><x:fldChar x:fldCharType="separate"/></x:r>'
                b"<x:r><x:t>last result</x:t></x:r>"
                b'<x:r><x:fldChar x:fldCharType="end"/></x:r></x:p>'
                b'<x:p><x:fldSimple x:instr=" INCLUDEPICTURE &quot;C:\\x.png&quot; ">'
                b"<x:r><x:t>picture</x:t></x:r></x:fldSimple></x:p>"
                b"</x:body></x:document>"
            ),
        },
    )
    neutralize_external(copy)
    assert "secret" not in _part(copy, "word/_rels/document.xml.rels")
    document = _part(copy, "word/document.xml")
    assert "secret" not in document
    assert "INCLUDEPICTURE" not in document
    assert "last result" in document


def test_a_part_in_utf16_is_neutralized_and_stays_utf16(tmp_path: Path) -> None:
    """XML parts may be UTF-16; one must not stop the copy from being made safe."""
    rels = (
        '<?xml version="1.0" encoding="UTF-16"?><Relationships xmlns="x">'
        '<Relationship Id="rId2" Type="t/image" Target="file:///C:/secret/a.png" '
        'TargetMode="External"/></Relationships>'
    )
    copy = _package(
        tmp_path / "copy.docx",
        {"word/_rels/document.xml.rels": rels.encode("utf-16")},
    )
    neutralize_external(copy)
    with zipfile.ZipFile(copy) as archive:
        data = archive.read("word/_rels/document.xml.rels")
    assert data.startswith((b"\xff\xfe", b"\xfe\xff"))
    assert "secret" not in data.decode("utf-16")
    assert "about:invalid" in data.decode("utf-16")
