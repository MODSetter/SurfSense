"""A cell's dropdown and its sheet's protection hold at write time, as Excel holds them when typing."""

import re
from pathlib import Path

import openpyxl
import pytest
from openpyxl.styles import Protection
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

from modules.artifacts.revised_copies.engines import excel
from modules.artifacts.revised_copies.engines.excel_inspection import inspect_workbook
from tests.unit.artifacts.revised_copies.office_fixtures import (
    check_workbook,
    parts,
    rewrite_part,
)

pytestmark = pytest.mark.unit

X14_VALIDATIONS = (
    b'<extLst><ext uri="{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}" '
    b'xmlns:x14="http://schemas.microsoft.com/office/spreadsheetml/2009/9/main">'
    b'<x14:dataValidations count="1" '
    b'xmlns:xm="http://schemas.microsoft.com/office/excel/2006/main">'
    b'<x14:dataValidation type="list" allowBlank="1" showErrorMessage="1">'
    b"<x14:formula1><xm:f>Lists!$B$1:$B$3</xm:f></x14:formula1>"
    b"<xm:sqref>F2:F4</xm:sqref></x14:dataValidation></x14:dataValidations>"
    b"</ext></extLst>"
)


@pytest.fixture
def questionnaire(tmp_path: Path) -> Path:
    """A requester's workbook: literal, range and named dropdowns, a protected sheet, a hidden list sheet."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Questions"
    sheet.append(["#", "Question", "Answer", "Scope", "Status", "Rating"])
    for number in range(1, 4):
        sheet.append([number, f"Question {number}?", None, None, None, None])
    lists = book.create_sheet("Lists")
    for row, (scope, rating) in enumerate(
        [("In scope", "High"), ("Out of scope", "Medium"), (None, "Low")], start=1
    ):
        lists.cell(row, 1, scope)
        lists.cell(row, 2, rating)
    lists.sheet_state = "hidden"
    book.defined_names["Statuses"] = DefinedName(
        "Statuses", attr_text="Lists!$A$1:$A$2"
    )
    for area, source in (
        ("C2:C4", '"Yes,No,N/A"'),
        ("D2:D4", "Lists!$A$1:$A$2"),
        ("E2:E4", "Statuses"),
    ):
        rule = DataValidation(
            type="list", formula1=source, allow_blank=True, showErrorMessage=True
        )
        rule.add(area)
        sheet.add_data_validation(rule)
    for row in range(2, 5):
        for column in "CDEF":
            sheet[f"{column}{row}"].protection = Protection(locked=False)
    sheet.protection.sheet = True
    path = tmp_path / "Questionnaire.xlsx"
    book.save(path)
    # Excel 2010 and later keep a dropdown fed from another sheet in x14 form.
    rewrite_part(
        path,
        "xl/worksheets/sheet1.xml",
        lambda data: data.replace(b"</worksheet>", X14_VALIDATIONS + b"</worksheet>"),
    )
    return path


def run(book: Path, tmp_path: Path, *operations: dict):
    """Applies the operations to a copy next to the test's files."""
    out = tmp_path / "out.xlsx"
    return excel.apply(book, list(operations), out), out


def test_inspection_lists_each_dropdowns_values_whatever_its_source(questionnaire):
    """A list from a literal, a range on another sheet, a defined name or Excel 2010's x14 form reads as its values."""
    found = inspect_workbook(questionnaire)

    questions = found.sheet("Questions")
    assert questions.protected
    assert [(rule.areas, rule.values) for rule in questions.dropdowns] == [
        (("C2:C4",), ("Yes", "No", "N/A")),
        (("D2:D4",), ("In scope", "Out of scope")),
        (("E2:E4",), ("In scope", "Out of scope")),
        (("F2:F4",), ("High", "Medium", "Low")),
    ]
    assert questions.dropdown_at("C3").values == ("Yes", "No", "N/A")
    assert questions.dropdown_at("B3") is None
    assert found.sheet("Lists").state == "hidden"


def test_inspection_tells_locked_from_unlocked_cells_on_a_protected_sheet(
    questionnaire,
):
    """On a protected sheet a cell is locked unless its style unlocks it."""
    questions = inspect_workbook(questionnaire).sheet("Questions")

    assert questions.locked("B2")
    assert not questions.locked("C2")


@pytest.mark.parametrize(
    ("cell", "value", "allowed"),
    [
        ("C2", "Maybe", "Yes, No, N/A"),
        ("C2", "yes", "Yes, No, N/A"),
        ("D3", "Partly", "In scope, Out of scope"),
        ("E4", "Done", "In scope, Out of scope"),
        ("F2", "Severe", "High, Medium, Low"),
    ],
)
def test_a_value_off_its_dropdown_is_refused_with_the_values_it_allows(
    questionnaire, tmp_path, cell, value, allowed
):
    """A value off the cell's list, even in another case, is refused and names what the list allows."""
    report, out = run(
        questionnaire,
        tmp_path,
        {"op": "set_cell", "sheet": "Questions", "cell": cell, "value": value},
    )

    assert not report.saved and not out.exists()
    refusal = report.outcomes[0]
    assert refusal.code == "VALUE_NOT_IN_LIST"
    assert refusal.values["allowed"] == allowed


def test_values_on_their_dropdowns_are_written_and_the_dropdowns_stay(
    questionnaire, tmp_path
):
    """Values on the list are written, and every dropdown and the protection stay in the file."""
    before = parts(questionnaire)["xl/worksheets/sheet1.xml"]

    report, out = run(
        questionnaire,
        tmp_path,
        {
            "op": "set_range",
            "sheet": "Questions",
            "range": "C2:F2",
            "values": [["N/A", "Out of scope", "In scope", "Low"]],
        },
    )

    assert report.saved
    check_workbook(out)
    written = openpyxl.load_workbook(out)["Questions"]
    assert [written[f"{c}2"].value for c in "CDEF"] == [
        "N/A",
        "Out of scope",
        "In scope",
        "Low",
    ]
    after = parts(out)["xl/worksheets/sheet1.xml"]
    for kept in (b"<dataValidations", b"<x14:dataValidations", b"<sheetProtection"):
        assert after.count(kept) == before.count(kept) == 1, kept
    assert inspect_workbook(out).sheet("Questions").dropdown_at("F2") is not None


def test_a_dropdown_cell_can_still_be_cleared(questionnaire, tmp_path):
    """Clearing a dropdown cell is allowed, as in Excel."""
    filled, first = run(
        questionnaire,
        tmp_path,
        {"op": "set_cell", "sheet": "Questions", "cell": "C2", "value": "Yes"},
    )
    assert filled.saved

    cleared = excel.apply(
        first,
        [{"op": "set_cell", "sheet": "Questions", "cell": "C2", "value": None}],
        tmp_path / "cleared.xlsx",
    )

    assert cleared.saved


def test_a_locked_cell_on_a_protected_sheet_is_refused(questionnaire, tmp_path):
    """Excel refuses typing into a locked cell of a protected sheet, and so does the engine."""
    report, _ = run(
        questionnaire,
        tmp_path,
        {"op": "set_cell", "sheet": "Questions", "cell": "B2", "value": "Edited?"},
    )

    assert not report.saved
    assert report.outcomes[0].code == "CELL_LOCKED"


def test_a_warning_dropdown_lets_an_off_list_value_through_as_excel_does(
    questionnaire, tmp_path
):
    """A list whose error style only warns lets another value through, as Excel does."""
    rewrite_part(
        questionnaire,
        "xl/worksheets/sheet1.xml",
        lambda data: data.replace(
            b'sqref="C2:C4" ', b'sqref="C2:C4" errorStyle="warning" '
        ),
    )

    report, _ = run(
        questionnaire,
        tmp_path,
        {"op": "set_cell", "sheet": "Questions", "cell": "C2", "value": "Partly"},
    )

    assert report.saved


def test_a_dropdown_that_shows_no_error_alert_lets_an_off_list_value_through(
    questionnaire, tmp_path
):
    """A list whose error alert is off accepts any typed value in Excel, and so here."""
    rewrite_part(
        questionnaire,
        "xl/worksheets/sheet1.xml",
        lambda data: re.sub(
            rb'(sqref="C2:C4"[^>]*)showErrorMessage="1"',
            rb'\1showErrorMessage="0"',
            data,
        ),
    )

    report, _ = run(
        questionnaire,
        tmp_path,
        {"op": "set_cell", "sheet": "Questions", "cell": "C2", "value": "Partly"},
    )

    assert report.saved


def test_a_list_of_formula_cells_offers_what_they_last_showed(questionnaire, tmp_path):
    """List cells that hold formulas offer their stored results, as Excel's dropdown does, and
    a value off them is still refused."""

    def as_formulas(data: bytes) -> bytes:
        for cell, text in ((b"A1", b"In scope"), (b"A2", b"Out of scope")):
            data = data.replace(
                b'<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (cell, text),
                b'<c r="%s" t="str"><f>UPPER("%s")</f><v>%s</v></c>'
                % (cell, text, text.upper()),
            )
        return data

    rewrite_part(questionnaire, "xl/worksheets/sheet2.xml", as_formulas)

    dropdown = inspect_workbook(questionnaire).sheet("Questions").dropdown_at("D2")
    report, _ = run(
        questionnaire,
        tmp_path,
        {"op": "set_cell", "sheet": "Questions", "cell": "D2", "value": "Partly"},
    )

    assert dropdown.values == ("IN SCOPE", "OUT OF SCOPE")
    assert report.outcomes[0].code == "VALUE_NOT_IN_LIST"


def test_a_list_name_scoped_to_a_sheet_after_a_chart_sheet_is_read(tmp_path):
    """A name's sheet scope counts chart sheets among the tabs, so the questions sheet's own
    list wins over the workbook's list of the same name."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Questions"
    sheet.append(["Question", "Answer"])
    sheet.append(["Question 1?", None])
    book.create_chartsheet("Chart", 0)
    lists = book.create_sheet("Lists")
    for row, (scoped, workbook_wide) in enumerate(
        [("Yes", "High"), ("No", "Low")], start=1
    ):
        lists.cell(row, 1, scoped)
        lists.cell(row, 2, workbook_wide)
    rule = DataValidation(type="list", formula1="Choices", allow_blank=True)
    rule.add("B2")
    sheet.add_data_validation(rule)
    path = tmp_path / "Charted.xlsx"
    book.save(path)
    rewrite_part(
        path,
        "xl/workbook.xml",
        lambda data: data.replace(
            b"<definedNames/>",
            b'<definedNames><definedName name="Choices">Lists!$B$1:$B$2</definedName>'
            b'<definedName name="Choices" localSheetId="1">Lists!$A$1:$A$2'
            b"</definedName></definedNames>",
        ),
    )

    questions = inspect_workbook(path).sheet("Questions")

    assert questions.dropdown_at("B2").values == ("Yes", "No")
