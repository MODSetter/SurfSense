"""Which PDFs are read from their own text layer, and which go to Docling whole."""

from pathlib import Path

import pypdfium2
import pytest

from tests import pdf_samples
from worker.ingestion.pdf_text_layer import TextLayer, read_text_layer

pytestmark = pytest.mark.unit

SWITCH = "SURFSENSE_LOCAL_PDF_TEXT_LAYER"
REPORT = pdf_samples.prose(6, seed=1)
FILED = "Case 1:20-cv-01234-ABC Document 45-3 Filed 03/12/20 Page {n} of {pages}"
STAMPS = {
    "a court's filing header": {"header": FILED},
    "a DocuSign envelope id": {
        "header": "DocuSign Envelope ID: 1A2B3C4D-1234-5678-ABCD-1234567890AB"
    },
    "a Bates number": {"footer": "CONFIDENTIAL ACME-00012{n}"},
    "a header and a Bates number": {
        "header": FILED,
        "footer": "CONFIDENTIAL ACME-00012{n}",
    },
}


@pytest.fixture(autouse=True)
def switch_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default a user has: no switch set."""
    monkeypatch.delenv(SWITCH, raising=False)


def read(tmp_path: Path, pdf: bytes) -> TextLayer:
    """The upload's text layer, read as ingest reads it."""
    path = tmp_path / "upload.pdf"
    path.write_bytes(pdf)
    return read_text_layer(path)


def left_edge(pdf: bytes, phrase: str) -> float:
    """Where on the page a phrase starts, in points from the left."""
    document = pypdfium2.PdfDocument(pdf)
    try:
        textpage = document[0].get_textpage()
        found = textpage.search(phrase).get_next()
        assert found is not None, phrase
        return textpage.get_charbox(found[0])[0]
    finally:
        document.close()


def test_a_born_digital_pdf_is_its_pages_and_paragraphs_a_blank_line_apart(
    tmp_path: Path,
) -> None:
    """The A/B's text arm, which answered better than Docling's, with a blank line
    where each paragraph ends."""
    pdf = pdf_samples.text_pages(REPORT[:2], REPORT[2:4], REPORT[4:])

    layer = read(tmp_path, pdf)

    assert layer.text == pdf_samples.set_text(REPORT[:2], REPORT[2:4], REPORT[4:])
    assert "\r" not in layer.text
    assert layer.text.count(REPORT[0][:30]) == 1


def test_a_two_column_page_reads_down_one_column_then_the_next(
    tmp_path: Path,
) -> None:
    """The order a reader takes: pdfium kept it on every 2- and 3-column stress page."""
    paragraphs = pdf_samples.prose(10, seed=2)
    pdf = pdf_samples.two_column_page(paragraphs)
    assert left_edge(pdf, "Paragraph 1 on") < 200 < left_edge(pdf, "Paragraph 10 on")

    layer = read(tmp_path, pdf)

    assert layer.text is not None
    starts = [layer.text.index(f"Paragraph {n} on") for n in range(1, 11)]
    assert starts == sorted(starts)
    assert layer.text.startswith("Coastal freight corridors")


@pytest.mark.parametrize("ocr_layer", [False, True], ids=["image only", "OCR layer"])
def test_a_scan_goes_to_docling(tmp_path: Path, ocr_layer: bool) -> None:
    """A scanner's invisible OCR may be garbage or another page's: only Docling's
    own OCR tells, and it read such layers back at 0.991."""
    pdf = pdf_samples.scanned_page(REPORT[:4], ocr_layer=ocr_layer)

    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == (
        "page 1 is ocr-layer:scanner" if ocr_layer else "page 1 is ocr:no-text"
    )


@pytest.mark.parametrize(
    ("answers", "ticked"),
    [
        ({"Claimant name": "Ingrid Solheim", "Policy number": ""}, False),
        ({"Claimant name": "", "Policy number": ""}, True),
    ],
    ids=["a field typed in", "a box ticked"],
)
def test_a_filled_in_form_goes_to_docling(
    tmp_path: Path, answers: dict[str, str], ticked: bool
) -> None:
    """The answers live in the fields, which the text layer never shows."""
    layer = read(tmp_path, pdf_samples.form(answers, ticked=ticked))

    assert layer.text is None
    assert layer.refused_because == "a form field holds an answer"


def test_a_form_nobody_filled_in_is_read_from_its_text_layer(tmp_path: Path) -> None:
    """An unticked box reports "Off" as its value; that is not an answer."""
    pdf = pdf_samples.form({"Claimant name": "", "Policy number": ""}, ticked=False)

    layer = read(tmp_path, pdf)

    assert layer.text is not None
    assert "Vehicle damage claim form" in layer.text
    assert "Claims are kept for seven years." in layer.text


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_a_turned_page_sends_the_whole_file_to_docling(
    tmp_path: Path, degrees: int
) -> None:
    """pdfium returns a turned page's lines last to first; one such page is enough."""
    pdf = pdf_samples.turned(
        pdf_samples.text_pages(REPORT[:2], REPORT[2:4]), page=1, degrees=degrees
    )

    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == f"page 2 is turned {degrees} degrees"


def test_a_section_cover_photo_with_its_title_is_read_from_the_text_layer(
    tmp_path: Path,
) -> None:
    """Docling's OCR of a cover photo added only noise, at the cost of a cold start."""
    pdf = pdf_samples.cover_page("Volume I Operating Budget", REPORT)

    layer = read(tmp_path, pdf)

    assert layer.text is not None
    assert layer.text.startswith("Volume I Operating Budget\n\n")
    assert REPORT[-1][:40] in layer.text


def test_a_full_page_photo_with_almost_no_text_goes_to_docling(
    tmp_path: Path,
) -> None:
    """Under 20 characters over a picture: only OCR can say what else it shows."""
    layer = read(tmp_path, pdf_samples.cover_page("Education", REPORT))

    assert layer.text is None
    assert layer.refused_because == "page 1 is ocr:no-text"


def test_a_pdf_with_no_page_of_running_text_goes_to_docling(tmp_path: Path) -> None:
    """A cover alone: its title is all the text layer has to give."""
    cover = pdf_samples.first_page(
        pdf_samples.cover_page("Volume I Operating Budget", REPORT)
    )

    layer = read(tmp_path, cover)

    assert layer.text is None
    assert layer.refused_because == "no page is ok:text"


@pytest.mark.parametrize("stamp", STAMPS.values(), ids=STAMPS)
def test_a_scan_with_live_text_stamped_on_it_goes_to_docling(
    tmp_path: Path, stamp: dict[str, str]
) -> None:
    """Court exhibits, DocuSign-completed scans and discovery productions: the
    stamp is the whole text layer, the page's text is in the picture."""
    scan = pdf_samples.scanned_page(REPORT[:4], ocr_layer=False)
    pdf = pdf_samples.stamped(pdf_samples.joined(scan, scan, scan), **stamp)

    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == "page 1 is ocr:no-text"


def test_a_brief_with_a_stamped_scan_for_an_exhibit_goes_to_docling(
    tmp_path: Path,
) -> None:
    """Read from the text layer, the exhibit would be its filing header alone."""
    exhibit = pdf_samples.stamped(
        pdf_samples.scanned_page(REPORT[:4], ocr_layer=False), header=FILED
    )
    brief = pdf_samples.text_pages(REPORT[:3], REPORT[3:])

    layer = read(tmp_path, pdf_samples.joined(brief, exhibit))

    assert layer.text is None
    assert layer.refused_because == "page 3 is ocr:no-text"


@pytest.mark.parametrize(
    "pdf",
    [
        pdf_samples.text_pages(REPORT[:3], REPORT[3:]),
        pdf_samples.illustrated(REPORT[:4]),
    ],
    ids=["text", "text and a photo"],
)
def test_running_headers_and_page_numbers_over_text_keep_the_text_layer(
    tmp_path: Path, pdf: bytes
) -> None:
    """The page's own text is live too, so the margins are not all it has."""
    pdf = pdf_samples.stamped(
        pdf, header="Harbour Annual Report 2025", footer="Page {n} of {pages}"
    )

    layer = read(tmp_path, pdf)

    assert layer.text is not None
    assert "Harbour Annual Report 2025" in layer.text
    assert REPORT[2][:40] in layer.text


@pytest.mark.parametrize(
    "footer",
    ["12", "Harbour Annual Report 2025 - page 3 of 12"],
    ids=["a page number", "a running footer"],
)
def test_outlined_lettering_under_a_live_footer_goes_to_docling(
    tmp_path: Path, footer: str
) -> None:
    """Fonts outlined for print, page numbers added after: Docling's OCR reads
    the outlines, where the text layer has only the footer."""
    pdf = pdf_samples.stamped(pdf_samples.outlined_page(REPORT[:4]), footer=footer)

    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == "page 1 is ocr:no-text"


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_a_scan_drawn_from_nested_forms_goes_to_docling(
    tmp_path: Path, depth: int
) -> None:
    """N-up imposition and a PDF included in a PDF nest the scan in forms."""
    scan = pdf_samples.nested(
        pdf_samples.scanned_page(REPORT[:4], ocr_layer=False), depth
    )
    pdf = pdf_samples.joined(pdf_samples.text_pages(REPORT[:3], REPORT[3:]), scan)

    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == "page 3 is ocr:no-text"


@pytest.mark.parametrize(
    ("pdf", "kind"),
    [
        (
            pdf_samples.scanned_page(REPORT[:4], ocr_layer=True),
            "ocr-layer:scanner",
        ),
        (
            pdf_samples.misencoded(pdf_samples.text_pages(REPORT), "e", chr(0xFFFD)),
            "ocr:garbled",
        ),
    ],
    ids=["a scanner's OCR layer", "a broken font map"],
)
def test_a_page_nested_in_forms_is_checked_like_any_other(
    tmp_path: Path, pdf: bytes, kind: str
) -> None:
    """Its text objects are two forms down, its characters on the page."""
    layer = read(tmp_path, pdf_samples.nested(pdf, 2))

    assert layer.text is None
    assert layer.refused_because == f"page 1 is {kind}"


def test_a_scan_whose_page_box_is_off_the_origin_goes_to_docling(
    tmp_path: Path,
) -> None:
    """The scan covers the page however far its box is from 0,0."""
    pdf = pdf_samples.moved(
        pdf_samples.scanned_page(REPORT[:4], ocr_layer=True), 400, 400
    )

    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == "page 1 is ocr-layer:scanner"


def test_a_text_page_whose_box_is_off_the_origin_keeps_the_text_layer(
    tmp_path: Path,
) -> None:
    """Its lines are measured from its own box, not from 0,0."""
    pdf = pdf_samples.text_pages(REPORT[:3], REPORT[3:])

    layer = read(tmp_path, pdf_samples.moved(pdf, 400, 400))

    assert layer.text == pdf_samples.set_text(REPORT[:3], REPORT[3:])


def test_a_word_hyphenated_at_a_lines_end_is_whole_again(tmp_path: Path) -> None:
    """pdfium leaves U+FFFE where it took out the line break: the embedder reads
    such a word as [UNK], and a search for it misses."""
    pdf = pdf_samples.lines_page(
        [
            "The orchestration layer for the Her-",
            "mes Agent keeps the life-",
            "cycle of the above-",
            "Referenced tasks from 2019-",
            "2020 on.",
        ]
    )

    layer = read(tmp_path, pdf)

    assert layer.text is not None
    assert "￾" not in layer.text
    assert "the Hermes Agent keeps the lifecycle of the above-Referenced" in (
        layer.text
    )
    assert "2019-\n2020 on." in layer.text


def test_a_control_code_from_a_broken_font_map_is_dropped(tmp_path: Path) -> None:
    """Too few to call the page garbled, and Word's XML refuses them in a draft."""
    pdf = pdf_samples.misencoded(
        pdf_samples.text_pages([*REPORT, "Approved on 12 September 2017."]),
        "7",
        chr(0x1A),
    )

    layer = read(tmp_path, pdf)

    assert layer.text is not None
    assert "Approved on 12 September 201." in layer.text
    assert not any(char < " " and char not in "\n\t" for char in layer.text)


@pytest.mark.parametrize(
    "pdf",
    [
        pdf_samples.text_pages(["#%&*+=<>|~^@$!?{}[]/() " * 30]),
        pdf_samples.misencoded(pdf_samples.text_pages(REPORT), "e", chr(0xFFFD)),
        pdf_samples.misencoded(pdf_samples.text_pages(REPORT), "e", chr(0x01)),
        pdf_samples.misencoded(pdf_samples.text_pages(REPORT), "e", chr(0xE000)),
    ],
    ids=["symbols", "replacement character", "control code", "private use"],
)
def test_garbage_in_the_text_layer_goes_to_docling(tmp_path: Path, pdf: bytes) -> None:
    """One letter in ten mapped to nothing readable is a broken font map."""
    layer = read(tmp_path, pdf)

    assert layer.text is None
    assert layer.refused_because == "page 1 is ocr:garbled"


def test_a_table_of_contents_is_not_garbage(tmp_path: Path) -> None:
    """Dot leaders leave a contents page 17% letters, below the garbage line."""
    chapters = ["Introduction", "Revenue", "Capital", "Debt service", "Staffing"]
    contents = [f"{name} {'.' * 60} {n}" for n, name in enumerate(chapters, 1)]

    layer = read(tmp_path, pdf_samples.text_pages(["Contents", *contents]))

    assert layer.text is not None
    assert "Debt service ....." in layer.text


def test_a_blank_page_keeps_the_text_layer(tmp_path: Path) -> None:
    """A page left blank between chapters has nothing for Docling to find."""
    pdf = pdf_samples.text_pages(REPORT[:2], [], REPORT[2:4])

    layer = read(tmp_path, pdf)

    assert layer.text == pdf_samples.set_text(REPORT[:2], [], REPORT[2:4])


@pytest.mark.parametrize(("shapes", "text_layer"), [(3, True), (30, False)])
def test_a_page_of_shapes_without_text_goes_to_docling(
    tmp_path: Path, shapes: int, text_layer: bool
) -> None:
    """Lettering turned into outlines is shapes Docling's OCR reads; a rule or two is not."""
    pdf = pdf_samples.joined(
        pdf_samples.text_pages(REPORT[:2]), pdf_samples.drawn_page(shapes)
    )

    layer = read(tmp_path, pdf)

    assert (layer.text is not None) is text_layer
    if not text_layer:
        assert layer.refused_because == "page 2 is ocr:no-text"


def test_a_pdf_with_no_text_at_all_goes_to_docling(tmp_path: Path) -> None:
    """Its text layer has nothing to give; Docling may still find figures."""
    layer = read(tmp_path, pdf_samples.drawn_page(1))

    assert layer.text is None
    assert layer.refused_because == "it has no text layer"


def test_a_file_pdfium_cannot_open_goes_to_docling(tmp_path: Path) -> None:
    """Docling then refuses it, or reads it, exactly as before."""
    layer = read(tmp_path, b"%PDF-1.7 not really")

    assert layer.text is None
    assert (layer.refused_because or "").startswith("pdfium could not read it")


@pytest.mark.parametrize(
    ("switch", "text_layer"),
    [
        (None, True),
        ("on", True),
        (" TRUE ", True),
        ("off", False),
        (" Off ", False),
        ("0", False),
        ("sometimes", False),
    ],
)
def test_the_switch_turns_the_text_layer_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    switch: str | None,
    text_layer: bool,
) -> None:
    """Off reads every PDF with Docling, as before; a value it cannot read is off."""
    if switch is not None:
        monkeypatch.setenv(SWITCH, switch)

    layer = read(tmp_path, pdf_samples.text_pages(REPORT))

    assert (layer.text is not None) is text_layer


# Page by page: the routing reads these to send Docling only the pages it must


def test_each_page_says_whether_the_text_layer_holds_its_text(tmp_path: Path) -> None:
    """A scan bound into a report is named; the pages around it keep their text."""
    first = pdf_samples.text_pages(REPORT[:2])
    last = pdf_samples.text_pages(REPORT[4:])
    scan = pdf_samples.scanned_page(REPORT[2:4], ocr_layer=False)

    layer = read(tmp_path, pdf_samples.joined(first, scan, last))

    assert [page.refused_because for page in layer.pages] == [
        None,
        "page 2 is ocr:no-text",
        None,
    ]
    assert [page.text for page in layer.pages] == [
        pdf_samples.set_text(REPORT[:2]),
        None,
        pdf_samples.set_text(REPORT[4:]),
    ]
    assert layer.refused_because == "page 2 is ocr:no-text"


def test_a_turned_page_is_named_and_the_others_still_read(tmp_path: Path) -> None:
    """Only the turned page's lines come last to first."""
    pages = [REPORT[:2], REPORT[2:4], REPORT[4:]]
    pdf = pdf_samples.turned(pdf_samples.text_pages(*pages), page=1, degrees=90)

    layer = read(tmp_path, pdf)

    assert [page.refused_because for page in layer.pages] == [
        None,
        "page 2 is turned 90 degrees",
        None,
    ]
    assert layer.pages[2].text == pdf_samples.set_text(pages[2])


def test_each_page_counts_the_path_segments_it_draws(tmp_path: Path) -> None:
    """A curve is four: where it starts and its three points."""
    pdf = pdf_samples.joined(
        pdf_samples.text_pages(REPORT[:2]), pdf_samples.drawn_page(10)
    )

    layer = read(tmp_path, pdf)

    assert [page.segments for page in layer.pages] == [0, 40]


def test_a_filled_in_form_names_no_page(tmp_path: Path) -> None:
    """Its answers are in its fields, whatever its pages hold: Docling reads it whole."""
    pdf = pdf_samples.form({"Claimant name": "Ingrid Solheim"}, ticked=False)

    assert read(tmp_path, pdf).pages == ()
