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


def _deck(script: str, images: dict[str, Path] | None = None) -> pptx.Presentation:
    result = run_document_script(
        script, output_name="document.pptx", images=images or {}
    )
    assert result.ok, f"{result.error}\n{result.traceback_tail}"
    return pptx.Presentation(BytesIO(result.output))


def _texts(slide: object) -> list[str]:
    return [s.text_frame.text for s in slide.shapes if s.has_text_frame]


def test_a_second_picture_under_one_heading_goes_on_to_a_slide_of_its_own(
    tmp_path: Path,
) -> None:
    """The second picture once got a negative height, which PowerPoint calls damaged."""
    square = tmp_path / "square.png"
    Image.new("RGB", (800, 800), "white").save(square)
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Site visit")\n'
        'doc.heading("Photos")\n'
        'doc.image("front", caption="The front gate")\n'
        'doc.image("back")\n'
        "doc.save()\n",
        {"front": square, "back": square},
    )

    slides = list(deck.slides)
    assert [s.shapes.title.text for s in slides] == ["Site visit", "Photos", "Photos"]
    for slide in slides[1:]:
        (picture,) = [s for s in slide.shapes if s.shape_type == MSO_SHAPE_TYPE.PICTURE]
        assert picture.height > 0
        assert picture.top + picture.height <= deck.slide_height
    assert "The front gate" in _texts(slides[1])


def test_a_page_break_in_a_deck_starts_a_slide_under_the_same_heading() -> None:
    """One script makes every format: a page break means a new slide in a deck."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Plan")\n'
        'doc.heading("Steps")\n'
        'doc.paragraph("First the pilot.")\n'
        "doc.page_break()\n"
        'doc.paragraph("Then every depot.")\n'
        "doc.save()\n"
    )

    slides = list(deck.slides)[1:]
    assert [s.shapes.title.text for s in slides] == ["Steps", "Steps"]
    assert "First the pilot." in " ".join(_texts(slides[0]))
    assert "Then every depot." in " ".join(_texts(slides[1]))


def test_a_long_table_in_a_deck_runs_on_with_its_header_and_bold_total() -> None:
    """Thirty rows and a total do not fit one slide: no row is lost or off the slide."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Costs")\n'
        'doc.heading("Every line")\n'
        "doc.table(\n"
        '    ["Item", "EUR"],\n'
        '    [[f"Item {n}", n * 10] for n in range(1, 31)],\n'
        '    total=["Total", 4650],\n'
        "    bold_total=True,\n"
        ")\n"
        "doc.save()\n"
    )

    shown: list[list[str]] = []
    total_bold = None
    for slide in list(deck.slides)[1:]:
        assert slide.shapes.title.text == "Every line"
        (frame,) = [s for s in slide.shapes if s.has_table]
        assert frame.top + frame.height <= deck.slide_height
        rows = [[cell.text for cell in row.cells] for row in frame.table.rows]
        assert rows[0] == ["Item", "EUR"]
        shown += rows[1:]
        for row in frame.table.rows:
            if row.cells[0].text == "Total":
                total_bold = row.cells[0].text_frame.paragraphs[0].runs[0].font.bold
    assert shown == [[f"Item {n}", f"{n * 10:,}"] for n in range(1, 31)] + [
        ["Total", "4,650"]
    ]
    assert total_bold is True


def test_speaker_notes_stay_with_the_slide_their_content_went_on_to(
    tmp_path: Path,
) -> None:
    """Two pictures under one heading make two slides, each with its own notes."""
    square = tmp_path / "square.png"
    Image.new("RGB", (800, 800), "white").save(square)
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Site visit")\n'
        'doc.heading("Photos")\n'
        'doc.image("front")\n'
        'doc.notes("This is the front gate.")\n'
        'doc.image("back")\n'
        'doc.notes("And the yard behind it.")\n'
        "doc.save()\n",
        {"front": square, "back": square},
    )

    notes = [s.notes_slide.notes_text_frame.text for s in list(deck.slides)[1:]]
    assert notes == ["This is the front gate.", "And the yard behind it."]


def test_a_list_longer_than_a_slide_runs_on_in_order_and_counts_on() -> None:
    """Forty steps and a table: no text box is taller than its slide."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Runbook")\n'
        'doc.heading("Steps")\n'
        'doc.numbered([f"Step {n}" for n in range(1, 41)])\n'
        'doc.table(["Owner", "Hours"], [["Ops", 12]])\n'
        "doc.save()\n"
    )

    steps: list[str] = []
    starts: list[str | None] = []
    for slide in list(deck.slides)[1:]:
        assert slide.shapes.title.text == "Steps"
        for shape in slide.shapes:
            assert shape.top + shape.height <= deck.slide_height
            if shape.has_text_frame and shape != slide.shapes.title:
                paragraphs = shape.text_frame.paragraphs
                steps += [p.text for p in paragraphs]
                number = paragraphs[0]._p.pPr.find(qn("a:buAutoNum"))
                starts.append(number.get("startAt") if number is not None else None)
    assert steps == [f"Step {n}" for n in range(1, 41)]
    assert starts[0] is None and starts[1:] == ["13", "25", "37"]
    assert any(s.has_table for s in list(deck.slides)[-1].shapes)


def _boxes(deck: pptx.Presentation) -> list[tuple[int, object]]:
    """Every text box below a title after the cover, with its slide's number."""
    return [
        (n, shape)
        for n, slide in enumerate(deck.slides)
        if n > 0
        for shape in slide.shapes
        if shape.has_text_frame and shape != slide.shapes.title
    ]


def test_an_item_the_room_left_cannot_hold_moves_to_a_slide_of_its_own() -> None:
    """Twelve lines of one bullet below an intro would run past the slide's foot."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Notes")\n'
        'doc.heading("Points")\n'
        'doc.paragraph("Intro")\n'
        'doc.bullets(["x" * 1200, "End"])\n'
        'doc.table(["A", "B"], [["1", "2"]])\n'
        "doc.save()\n"
    )

    for _, shape in _boxes(deck):
        assert shape.top + shape.height <= deck.slide_height
    where = {s.text_frame.paragraphs[0].text[:5]: n for n, s in _boxes(deck)}
    assert where["Intro"] < where["xxxxx"]


def test_a_paragraph_longer_than_a_slide_goes_on_in_pieces_between_words() -> None:
    """A thousand words take several slides, every word kept and in order."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Essay")\n'
        'doc.heading("Body")\n'
        'doc.paragraph(" ".join(f"w{n}" for n in range(1000)))\n'
        'doc.table(["A"], [["1"]])\n'
        "doc.save()\n"
    )

    words: list[str] = []
    for _, shape in _boxes(deck):
        assert shape.top + shape.height <= deck.slide_height
        words += shape.text_frame.text.split()
    assert words == [f"w{n}" for n in range(1000)]
    assert len(deck.slides) > 3


def test_a_long_numbered_item_carries_on_unnumbered_and_the_next_counts_on() -> None:
    """A piece that carries on an item has no number of its own."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Steps")\n'
        'doc.heading("How")\n'
        'doc.numbered(["Short", "y " * 1000, "After"])\n'
        'doc.table(["A"], [["1"]])\n'
        "doc.save()\n"
    )

    marks = {}
    for _, shape in _boxes(deck):
        for paragraph in shape.text_frame.paragraphs:
            p_pr = paragraph._p.pPr
            number = p_pr.find(qn("a:buAutoNum"))
            marks.setdefault(paragraph.text.strip()[:5], []).append(
                None if number is None else number.get("startAt", "1")
            )
    assert marks["Short"] == ["1"]
    assert marks["After"] == ["3"]
    # The long item's first piece is numbered 2; its other pieces have no number.
    assert marks["y y y"][0] is not None and set(marks["y y y"][1:]) == {None}


def test_bold_across_a_piece_boundary_stays_bold_with_no_marks_shown() -> None:
    """The markup is read before the text is split, so `**` never shows."""
    deck = _deck(
        "from surfsense_docs import Doc\n"
        'doc = Doc("Essay")\n'
        'doc.heading("Body")\n'
        'doc.paragraph("**" + "word " * 1000 + "**")\n'
        'doc.paragraph("Short **and bold** text")\n'
        'doc.table(["A"], [["1"]])\n'
        "doc.save()\n"
    )

    runs = [
        run
        for _, shape in _boxes(deck)
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    ]
    assert len({id(shape) for _, shape in _boxes(deck)}) > 2
    assert not any("*" in run.text for run in runs)
    words = [run for run in runs if run.text.strip().startswith("word")]
    assert words and all(run.font.bold for run in words)
    short = [run.text for run in runs if run.font.bold and "and bold" in run.text]
    assert short == ["and bold"]
