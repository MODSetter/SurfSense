"""A new sheet goes after the requester's own, which keep their bytes: answers' sources
and exceptions travel in the file without moving anything the requester imports."""

from pathlib import Path

import openpyxl
import pytest

from modules.artifacts.revised_copies.engines import excel
from modules.artifacts.revised_copies.engines.excel_refs import MAX_COLUMN
from tests.unit.artifacts.revised_copies.office_fixtures import (
    build_workbook,
    check_workbook,
    parts,
)

pytestmark = pytest.mark.unit

ROWS = [
    ["Row", "Answer", "Quote"],
    [2, "Yes", 'Access is "least privilege" by role.'],
    [3, None, True],
]


@pytest.fixture
def book(tmp_path: Path) -> Path:
    """A real workbook with charts, shapes and a table, as in the engine's own tests."""
    return build_workbook(tmp_path / "Sales.xlsx", image=tmp_path / "logo.png")


def run(book: Path, tmp_path: Path, *operations: dict):
    """Applies the operations to a copy next to the test's files."""
    out = tmp_path / "out.xlsx"
    return excel.apply(book, list(operations), out), out


def test_a_new_sheet_holds_its_rows_after_the_others_and_leaves_them_byte_identical(
    book, tmp_path
):
    """A new sheet goes last with its rows, and every part but the workbook's sheet list keeps its bytes."""
    before = parts(book)

    report, out = run(
        book,
        tmp_path,
        {"op": "add_sheet", "sheet": "SurfSense answers", "values": ROWS},
    )

    assert report.saved
    check_workbook(out)
    opened = openpyxl.load_workbook(out)
    assert opened.sheetnames == ["Data", "Table", "SurfSense answers"]
    added = opened["SurfSense answers"]
    assert [[c.value for c in row] for row in added.iter_rows()] == ROWS
    after = parts(out)
    for name, data in before.items():
        if name not in (
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "[Content_Types].xml",
        ):
            assert after[name] == data, name


def test_answers_and_their_sources_sheet_go_in_one_call(book, tmp_path):
    """Cell edits and a new sheet apply together, all or nothing."""
    report, out = run(
        book,
        tmp_path,
        {"op": "set_cell", "sheet": "Data", "cell": "B3", "value": 25},
        {
            "op": "add_sheet",
            "sheet": "Sources",
            "values": [["Cell", "Source"], ["B3", "Plan, s. 4"]],
        },
    )

    assert report.saved and report.applied == 2
    opened = openpyxl.load_workbook(out)
    assert opened["Data"]["B3"].value == 25
    assert opened["Sources"]["B2"].value == "Plan, s. 4"


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("data", "SHEET_EXISTS"),
        ("Answers: final", "BAD_SHEET_NAME"),
        ("A" * 32, "BAD_SHEET_NAME"),
        ("'Quoted", "BAD_SHEET_NAME"),
        ("History", "BAD_SHEET_NAME"),
    ],
)
def test_a_sheet_name_excel_would_refuse_saves_nothing(book, tmp_path, name, code):
    """A name Excel refuses, or one already taken in any case, saves nothing."""
    report, out = run(
        book, tmp_path, {"op": "add_sheet", "sheet": name, "values": [["x"]]}
    )

    assert not report.saved and not out.exists()
    assert report.outcomes[0].code == code


def test_a_row_wider_than_excel_s_grid_saves_nothing(book, tmp_path):
    """A row with a value past column XFD saves nothing, and the model is told which field to fix."""
    report, out = run(
        book,
        tmp_path,
        {"op": "add_sheet", "sheet": "Sources", "values": [["x"] * (MAX_COLUMN + 1)]},
    )

    assert not report.saved and not out.exists()
    assert report.outcomes[0].code == "BAD_OPERATION"
    assert report.outcomes[0].values == {"field": "values"}


def test_a_macro_workbook_keeps_its_macros_when_a_sheet_is_added(tmp_path):
    """An .xlsm keeps its VBA project byte for byte when a sheet is added."""
    import xlsxwriter

    macros = tmp_path / "vbaProject.bin"
    macros.write_bytes(bytes(range(256)) * 8)
    path = tmp_path / "Macros.xlsm"
    book = xlsxwriter.Workbook(str(path))
    book.add_worksheet("Sheet1").write("A1", 1)
    book.add_vba_project(str(macros))
    book.close()

    report, out = run(
        path, tmp_path, {"op": "add_sheet", "sheet": "Exceptions", "values": [["None"]]}
    )

    assert report.saved
    assert parts(out)["xl/vbaProject.bin"] == parts(path)["xl/vbaProject.bin"]
    check_workbook(out)
    assert openpyxl.load_workbook(out, keep_vba=True).sheetnames == [
        "Sheet1",
        "Exceptions",
    ]
