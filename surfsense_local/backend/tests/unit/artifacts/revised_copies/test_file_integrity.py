"""Files Office would refuse or repair: the engines must neither write them nor crash on them."""

import zipfile
from pathlib import Path

import pytest
from lxml import etree

from modules.artifacts.revised_copies.engines import excel, powerpoint, word
from modules.artifacts.revised_copies.engines.package import (
    PackageRefusedError,
    open_package,
)
from tests.unit.artifacts.revised_copies.office_fixtures import (
    add_part,
    build_deck,
    build_workbook,
    check_deck,
    check_workbook,
    rewrite_part,
)
from tests.unit.artifacts.revised_copies.word_fixtures import (
    DATE,
    docx_with_body,
    para,
    plain_text,
    run,
    structure_problems,
    w,
)

pytestmark = pytest.mark.unit

GRID = '<w:tblPr/><w:tblGrid><w:gridCol w:w="2000"/><w:gridCol w:w="2000"/></w:tblGrid>'


def _tracked_row(tag: str, id_: int, *cells: str) -> str:
    """A table row another author inserted or deleted, as XML."""
    mark = f'<w:{tag} w:id="{id_}" w:author="Bob" w:date="{DATE}"/>'
    return (
        f"<w:tr><w:trPr>{mark}</w:trPr>"
        + "".join(f"<w:tc>{para(run(text))}</w:tc>" for text in cells)
        + "</w:tr>"
    )


def _tables(path: Path) -> list[etree._Element]:
    with zipfile.ZipFile(path) as archive:
        root = etree.fromstring(archive.read("word/document.xml"))
    return list(root.iter(w("tbl")))


def _row_and_cell_counts(path: Path) -> list[list[int]]:
    return [
        [len(row.findall(w("tc"))) for row in table.findall(w("tr"))]
        for table in _tables(path)
    ]


@pytest.mark.parametrize(
    ("tag", "decide"),
    [("ins", word.reject_all), ("del", word.accept_all)],
)
def test_a_table_whose_every_row_goes_is_removed_not_left_empty(tmp_path, tag, decide):
    """Word repairs a w:tbl with no w:tr; a table whose rows all go must go with them."""
    source = docx_with_body(
        tmp_path,
        para(run("Before."))
        + f"<w:tbl>{GRID}"
        + _tracked_row(tag, 1, "A1", "B1")
        + _tracked_row(tag, 2, "A2", "B2")
        + "</w:tbl>"
        + para(run("After.")),
    )
    out = tmp_path / "decided.docx"

    decide(source, out)

    assert _tables(out) == []
    assert plain_text(out) == ["Before.", "After."]
    assert structure_problems(out) == []


def test_a_row_whose_every_cell_goes_is_removed_not_left_empty(tmp_path):
    """Word repairs a w:tr with no w:tc; accepting deleted cells must not leave one."""
    deleted_cell = (
        '<w:tc><w:tcPr><w:cellDel w:id="{id}" w:author="Bob" w:date="'
        + DATE
        + '"/></w:tcPr>'
        + para(run("{text}"))
        + "</w:tc>"
    )
    source = docx_with_body(
        tmp_path,
        f"<w:tbl>{GRID}<w:tr>"
        + f"<w:tc>{para(run('Kept'))}</w:tc><w:tc>{para(run('Also kept'))}</w:tc>"
        + "</w:tr><w:tr>"
        + deleted_cell.format(id=3, text="Gone one")
        + deleted_cell.format(id=4, text="Gone two")
        + "</w:tr></w:tbl>"
        + para(run("After.")),
    )
    out = tmp_path / "accepted.docx"

    word.accept_all(source, out)

    assert _row_and_cell_counts(out) == [[2]]
    assert structure_problems(out) == []


def test_a_damaged_compressed_part_is_a_refusal_not_a_crash(tmp_path):
    """A corrupt deflate stream refuses the file with a code the tool can report."""
    source = docx_with_body(tmp_path, para(run("Hello world.")))
    data = bytearray(source.read_bytes())
    with zipfile.ZipFile(source) as archive:
        info = archive.getinfo("word/document.xml")
    start = info.header_offset + 30 + len(info.filename) + len(info.extra)
    data[start + 4 : start + 24] = b"\xff" * 20
    damaged = tmp_path / "damaged.docx"
    damaged.write_bytes(bytes(data))

    with pytest.raises(PackageRefusedError) as refused:
        word.apply(
            damaged,
            [{"op": "replace_text", "quote": "Hello", "text": "Bye"}],
            tmp_path / "out.docx",
        )

    assert refused.value.code == "NOT_A_PACKAGE"
    assert refused.value.values == {"part": "word/document.xml"}
    with pytest.raises(PackageRefusedError):
        open_package(damaged).read("word/document.xml")


@pytest.fixture
def book(tmp_path: Path) -> Path:
    """A real workbook with charts, shapes, merges and shared formulas."""
    return build_workbook(tmp_path / "Sales.xlsx", image=tmp_path / "logo.png")


@pytest.mark.parametrize(
    "formula",
    [
        "=SUM(B2:B6",
        "=SUM(B2:B6))",
        '=IF(B2>1,"yes,B3)',
        "='Data!B2",
        "=SUM({1,2,3)",
        "=B2\x01",
    ],
)
def test_a_formula_excel_cannot_parse_is_refused_before_it_reaches_the_sheet(
    book, tmp_path, formula
):
    """Excel repairs a sheet holding an unparsable formula, so the edit names the field instead."""
    out = tmp_path / "out.xlsx"

    report = excel.apply(
        book,
        [{"op": "set_cell", "sheet": "Data", "cell": "B8", "formula": formula}],
        out,
    )

    assert report.outcomes[0].code == "BAD_OPERATION"
    assert report.outcomes[0].values == {"field": "formula"}
    assert not out.exists()


def test_balanced_formulas_with_strings_sheets_and_arrays_still_go_in(book, tmp_path):
    """Brackets inside text and quoted sheet names do not count; array constants are fine."""
    out = tmp_path / "out.xlsx"
    formulas = [
        '=IF(B2>1,"(open",")close")',
        "='Data'!B2+'It''s'!A1",
        "=SUM({1,2,3})",
        "=Table1[[#This Row],[Cost]]",
    ]

    report = excel.apply(
        book,
        [
            {"op": "set_cell", "sheet": "Data", "cell": f"B{8 + i}", "formula": f}
            for i, f in enumerate(formulas)
        ],
        out,
    )

    assert report.saved, report.as_text()
    check_workbook(out)


def test_a_number_beyond_what_excel_stores_is_refused_not_a_crash(book, tmp_path):
    """Excel keeps IEEE doubles; an integer too large for one is a bad value."""
    out = tmp_path / "out.xlsx"

    report = excel.apply(
        book,
        [{"op": "set_cell", "sheet": "Data", "cell": "B3", "value": 10**400}],
        out,
    )

    assert report.outcomes[0].code == "BAD_OPERATION"
    assert report.outcomes[0].values == {"field": "value"}
    assert not out.exists()


def test_deleting_a_slide_the_outline_view_lists_leaves_no_dangling_r_id(tmp_path):
    """PowerPoint saves collapsed outline slides in viewProps by r:id; deleting one must drop its entry."""
    deck = build_deck(tmp_path / "Deck.pptx", image=tmp_path / "logo.png")
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
    add_part(
        deck,
        "ppt/_rels/viewProps.xml.rels",
        (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{rel}" Target="slides/slide1.xml"/>'
            f'<Relationship Id="rId2" Type="{rel}" Target="slides/slide2.xml"/>'
            "</Relationships>"
        ).encode(),
    )
    rewrite_part(
        deck,
        "ppt/viewProps.xml",
        lambda data: data.replace(
            b"</p:slideViewPr>",
            b'</p:slideViewPr><p:outlineViewPr><p:cViewPr><p:scale><a:sx n="33" d="100"/>'
            b'<a:sy n="33" d="100"/></p:scale><p:origin x="0" y="0"/></p:cViewPr>'
            b'<p:sldLst><p:sld r:id="rId1" collapse="1"/><p:sld r:id="rId2" collapse="1"/>'
            b"</p:sldLst></p:outlineViewPr>",
        ),
    )
    check_deck(deck)
    out = tmp_path / "out.pptx"

    report = powerpoint.apply(deck, [{"op": "delete_slide", "slide": 2}], out)

    assert report.saved, report.as_text()
    check_deck(out)
