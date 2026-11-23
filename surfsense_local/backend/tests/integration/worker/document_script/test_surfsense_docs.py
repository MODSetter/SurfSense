"""The surfsense_docs helper as a document script uses it: copied into the run folder,
imported by name, saving a PDF, a Word document or a deck at OUTPUT_PATH."""

from io import BytesIO
from pathlib import Path

import docx
import pptx
import pypdfium2
import pytest
from PIL import Image
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

from worker.document_script.run import run_document_script

pytestmark = pytest.mark.integration

PLAN = """\
from surfsense_docs import Doc

doc = Doc("Spring plan: Elm Road & Co <garden>", subtitle="For the committee"{page})
doc.notes("Welcome everyone.")
doc.heading("What changes")
doc.paragraph("Opens on **12 April**, *two weeks* earlier.")
doc.bullets(["Members water their own plots", "Shared tools stay in the shed"])
doc.numbered(["Clear the beds", "Plant"])
doc.notes("Mention the water rota.")
doc.heading("Budget")
doc.table(
    ["Item", "Cost (USD)"],
    [["Raised beds", 1200], ["Soil", "450"], ["Hand tools", 300]],
    total=["Total", "1,950"],
    bold_total=True,
    after=[["Water, each month", 40]],
)
doc.chart("bar", ["Beds", "Soil", "Tools"], [1200, "450", "EUR 300"], title="Costs")
doc.save()
"""


def _render(output_name: str, script: str = PLAN.format(page="")) -> bytes:
    result = run_document_script(script, output_name=output_name, images={})
    assert result.ok, f"{result.error}\n{result.traceback_tail}"
    return result.output


def _pdf_text_and_size(output: bytes) -> tuple[str, tuple[int, int]]:
    pdf = pypdfium2.PdfDocument(output)
    try:
        text = "".join(page.get_textpage().get_text_range() for page in pdf)
        first = pdf[0]
        return text, (round(first.get_width()), round(first.get_height()))
    finally:
        pdf.close()


def test_a_pdf_keeps_the_sources_characters_and_lists_the_rows_in_order() -> None:
    """Text from a source reaches the page as written, not read as markup."""
    text, size = _pdf_text_and_size(_render("document.pdf"))

    assert size == (595, 842)  # A4
    assert "Elm Road & Co <garden>" in text
    for before, after in (("Hand tools", "Total"), ("1,950", "Water, each month")):
        assert text.index(before) < text.index(after)


def test_letter_pages_are_us_letter_in_a_pdf_and_a_word_document() -> None:
    """A reader in the US or Canada gets the paper they print on."""
    script = PLAN.format(page=", letter=True")

    _, size = _pdf_text_and_size(_render("document.pdf", script))
    section = docx.Document(BytesIO(_render("document.docx", script))).sections[0]

    assert size == (612, 792)
    assert (round(section.page_width.cm, 2), round(section.page_height.cm, 2)) == (
        21.59,
        27.94,
    )


def test_a_word_document_uses_real_heading_and_list_styles_on_a4() -> None:
    """Word's navigation and numbering work on what the helper writes."""
    document = docx.Document(BytesIO(_render("document.docx")))

    styles = {p.text: p.style.name for p in document.paragraphs if p.text}
    assert styles["What changes"] == "Heading 1"
    assert styles["Members water their own plots"] == "List Bullet"
    assert styles["Plant"] == "List Number"
    assert "Welcome everyone." not in styles  # speaker notes stay out of a document
    section = document.sections[0]
    assert (round(section.page_width.cm, 1), round(section.page_height.cm, 1)) == (
        21.0,
        29.7,
    )
    rows = [[cell.text for cell in row.cells] for row in document.tables[0].rows]
    assert rows[-2:] == [["Total", "1,950"], ["Water, each month", "40"]]
    total = document.tables[0].rows[-2].cells[0].paragraphs[0].runs[0]
    assert total.bold is True
    assert len(document.inline_shapes) == 1  # the chart


def test_a_deck_is_16_9_with_list_formatting_and_notes_on_their_slides() -> None:
    """PowerPoint draws the bullets; a typed bullet would show twice."""
    deck = pptx.Presentation(BytesIO(_render("document.pptx")))

    assert round(deck.slide_width / deck.slide_height, 2) == 1.78
    slides = list(deck.slides)
    assert [s.shapes.title.text for s in slides] == [
        "Spring plan: Elm Road & Co <garden>",
        "What changes",
        "Budget",
    ]
    notes = [
        s.notes_slide.notes_text_frame.text if s.has_notes_slide else "" for s in slides
    ]
    assert notes == ["Welcome everyone.", "Mention the water rota.", ""]
    body = slides[1].placeholders[1].text_frame.paragraphs
    texts = [p.text for p in body]
    assert "Members water their own plots" in texts
    assert not any(t.startswith(("•", "-", "1.")) for t in texts)
    marks = [
        child.tag
        for p in body
        for child in p._p.get_or_add_pPr()
        if child.tag in (qn("a:buChar"), qn("a:buAutoNum"), qn("a:buNone"))
    ]
    assert marks == [
        qn("a:buNone"),
        qn("a:buChar"),
        qn("a:buChar"),
        qn("a:buAutoNum"),
        qn("a:buAutoNum"),
    ]
    budget = slides[2]
    assert any(shape.has_table for shape in budget.shapes)
    # The chart is drawn with matplotlib and placed as a picture.
    assert any(s.shape_type == MSO_SHAPE_TYPE.PICTURE for s in budget.shapes)


def test_a_total_given_as_a_label_adds_up_each_number_column_and_skips_text() -> None:
    """As a spreadsheet's SUM does: "1,250 a month" is text, not a number."""
    script = """\
from surfsense_docs import Doc

doc = Doc("Costs")
doc.table(
    ["Item", "One-off (EUR)", "Note"],
    [["Beds", 1200, "paid"], ["Soil", "EUR 450", "due"], ["Rota", "1,250 a month", "-"]],
    total="Total",
)
doc.save()
"""
    document = docx.Document(BytesIO(_render("document.docx", script)))

    rows = [[cell.text for cell in row.cells] for row in document.tables[0].rows]
    assert rows[-1] == ["Total", "1,650", ""]


def test_a_chart_value_that_is_not_a_number_fails_with_what_to_fix() -> None:
    """The run fails on the call that has it, naming the value."""
    script = 'from surfsense_docs import Doc\nDoc("x").chart("bar", ["a"], ["soon"])\n'

    result = run_document_script(script, output_name="document.pdf", images={})

    assert not result.ok
    assert "a chart's values are numbers, not 'soon'" in (
        f"{result.error}\n{result.traceback_tail}"
    )


def test_a_tall_picture_is_scaled_to_fit_a_page(tmp_path: Path) -> None:
    """At the text width a long scan would run past the page, which ReportLab refuses."""
    tall = tmp_path / "scan.png"
    Image.new("RGB", (200, 1600), "white").save(tall)
    script = (
        "from surfsense_docs import Doc\n"
        'doc = Doc("Scan")\n'
        'doc.image("scan", caption="The scanned form")\n'
        "doc.save()\n"
    )

    pdf = run_document_script(script, output_name="document.pdf", images={"scan": tall})
    word = run_document_script(
        script, output_name="document.docx", images={"scan": tall}
    )

    assert pdf.ok, f"{pdf.error}\n{pdf.traceback_tail}"
    assert word.ok, f"{word.error}\n{word.traceback_tail}"
    document = docx.Document(BytesIO(word.output))
    section = document.sections[0]
    room = section.page_height - section.top_margin - section.bottom_margin
    assert document.inline_shapes[0].height <= room
