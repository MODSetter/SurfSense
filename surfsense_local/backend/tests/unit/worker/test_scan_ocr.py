"""OCR-first on scans: which pages its text stands for, how that text reads, and
which pages still go to Docling. No OCR runs: pages are made of boxes."""

from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest
from PIL import Image

from modules.documents.models import Document
from modules.documents.tasks import PRIORITY_INTERACTIVE
from worker.ingestion.pdf_reading import ocr_first
from worker.ingestion.pdf_reading.ocr_kept import forget_reading
from worker.ingestion.pdf_text_layer import LayerPage, TextLayer
from worker.ingestion.pdf_text_layer.page_triage import PageKind
from worker.ingestion.scan_ocr import switch
from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import Line, OcrPage, PageVerdict, Word
from worker.ingestion.scan_ocr.upright import read_upright
from worker.jobs import JobCancelledError, JobYieldedError

pytestmark = pytest.mark.unit

WIDTH, HEIGHT = 1786, 2526
WORD_H = 30.0


def line(text: str, y: float, x: float = 100.0, gap: float = 12.0) -> Line:
    """Words left to right on one line, `gap` pixels apart."""
    words = []
    at = x
    for piece in text.split():
        w = 18.0 * len(piece)
        words.append(Word(piece, at, y, w, WORD_H))
        at += w + gap
    return Line(text, tuple(words))


def page(*lines: Line, ink: float = 0.08, confidence: float | None = None) -> OcrPage:
    """A page of these lines, as an engine reads it."""
    return OcrPage(WIDTH, HEIGHT, tuple(lines), ink, "en-US", confidence)


def prose(lines: int = 12, start: float = 200.0) -> list[Line]:
    """Lines of running text, one under another."""
    return [
        line(
            f"The council heard the report on line {n} and voted to adopt it.",
            start + 45 * n,
        )
        for n in range(lines)
    ]


def test_running_text_is_text() -> None:
    """Running text is what OCR's text can stand for."""
    assert page(*prose()).verdict() is PageVerdict.TEXT


def test_prose_with_amounts_and_dates_is_still_text() -> None:
    """Justified prose with $5,000 and 12/10/98 in it is not a table."""
    lines = [
        *prose(8),
        line("The grant of $5,000 was paid on 12/10/98 to the district.", 600),
        line("A further $1,250 followed in 1999, as the board agreed.", 645),
    ]
    assert page(*lines).verdict() is PageVerdict.TEXT


def rows(n: int = 7) -> list[Line]:
    """A table's rows, each kept as one line with its cells far apart."""
    return [
        line(f"Item {k} 1,{k}00 2,{k}50 3,{k}75", 300 + 45 * k, gap=200.0)
        for k in range(1, n + 1)
    ]


def test_a_table_stays_with_ocr() -> None:
    """Its rows answered better than Docling's Markdown, which drops text."""
    assert page(*prose(3), *rows(), confidence=0.97).verdict() is PageVerdict.TEXT


def test_too_little_text_on_an_inked_page_is_too_little() -> None:
    """Handwriting or a photo: Docling runs the same OCR, so it stays."""
    assert page(line("Fig. 3", 300), ink=0.2).verdict() is PageVerdict.TOO_LITTLE


def test_a_blank_page_is_blank() -> None:
    """No text and almost no ink: blank paper, not a misread."""
    assert page(ink=0.001).verdict() is PageVerdict.BLANK


def test_garbled_output_goes_to_docling() -> None:
    """Mostly symbols: the engine misread the page."""
    noise = [
        line("~~ ^^ ;; || ~~ ^^ ;; || ~~ ^^ ;; ||", 300 + 45 * n) for n in range(5)
    ]
    assert page(*noise).verdict() is PageVerdict.GARBLED


def sideways() -> OcrPage:
    """What an engine with no confidence made of a sideways photo of prose."""
    strokes = [line("O 00 o c 0 O o 00 c O 0 o c 00 O", 300 + 45 * n) for n in range(6)]
    return page(*strokes)


def test_a_page_read_sideways_is_garbled_and_looks_sideways() -> None:
    """Letters and digits all, so the alnum guard passes it; few are words."""
    assert sideways().verdict() is PageVerdict.GARBLED
    assert sideways().looks_sideways()
    assert not page(*prose()).looks_sideways()


def test_a_page_of_figures_stands_on_the_engines_confidence() -> None:
    """Few words but long tokens: not sideways; with no confidence the word share
    sends it to Docling, as today."""
    figures = [
        line(f"{n},100 {n},250 {n}.5% 1,{n}00", 300 + 45 * n, gap=200.0)
        for n in range(8)
    ]
    assert page(*figures, confidence=0.97).verdict() is PageVerdict.TEXT
    assert page(*figures).verdict() is PageVerdict.GARBLED
    assert not page(*figures).looks_sideways()


def test_an_unsure_engine_means_a_garbled_page_read_sideways() -> None:
    """RapidOCR's confidence fell to 0.56-0.79 on sideways photos."""
    assert page(*prose(), confidence=0.6).verdict() is PageVerdict.GARBLED
    assert page(*prose(), confidence=0.6).looks_sideways()
    assert not page(*prose(), confidence=0.97).looks_sideways()


def test_a_sideways_page_is_read_again_turned(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first turn that reads as text wins; an upright page is read once."""
    readings = iter([sideways(), page(*prose()), sideways(), sideways()])
    reader = StubReader({})
    reader.read = lambda frames: ((f, next(readings)) for f in frames)  # type: ignore[method-assign]
    frame = Frame(1, Image.new("L", (40, 20), 0), 0.5)

    [(turned, read)] = list(read_upright(reader, [frame]))

    assert read.verdict() is PageVerdict.TEXT
    assert turned.image.size == (20, 40)


def test_a_hyphen_at_a_line_end_joins_the_next_word() -> None:
    """A word broken over a line reads whole, as the chunker and search want it."""
    lines = [line("The board approved the ap-", 200), line("plication in full.", 245)]
    assert page(*lines).text() == "The board approved the application in full."


def test_a_wide_gap_starts_a_paragraph() -> None:
    """A blank line where the page has one, so passages break there."""
    first = [line(f"First paragraph line {n}.", 200 + 45 * n) for n in range(4)]
    second = [line(f"Second paragraph line {n}.", 500 + 45 * n) for n in range(4)]
    text = page(*first, *second).text()

    assert "line 3.\n\nSecond paragraph line 0." in text
    assert "line 0.\nFirst paragraph line 1." in text


def test_the_switch_picks_the_reader_and_is_off_when_unclear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any case and spaces; a value nobody meant turns OCR-first off."""
    monkeypatch.delenv("SURFSENSE_LOCAL_SCAN_OCR", raising=False)
    assert switch.scan_ocr_choice() is switch.ScanOcr.AUTO
    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", " RapidOCR ")
    assert switch.scan_ocr_choice() is switch.ScanOcr.RAPIDOCR
    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "OFF")
    assert switch.scan_ocr_choice() is switch.ScanOcr.OFF
    monkeypatch.setenv("SURFSENSE_LOCAL_SCAN_OCR", "system")
    assert switch.scan_ocr_choice() is switch.ScanOcr.OFF


class StubReader:
    """OCR's pages by page number, as a system engine would give them."""

    name = "Stub OCR"
    language = "en-US"
    max_side = 10_000

    def __init__(self, pages: dict[int, OcrPage]) -> None:
        self.pages = pages
        self.asked: list[int] = []

    def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
        for frame in frames:
            self.asked.append(frame.number)
            yield frame, self.pages[frame.number]


@pytest.fixture
def ocr(monkeypatch: pytest.MonkeyPatch) -> dict[int, OcrPage]:
    """Pages the stub reads; frames are blank pictures, never a real render."""
    pages: dict[int, OcrPage] = {}
    reader = StubReader(pages)

    def frames(_original: Path, numbers: list[int], _max_side: int) -> Iterator[Frame]:
        for number in numbers:
            yield Frame(number, Image.new("L", (10, 10), 255), 0.0)

    monkeypatch.setattr(ocr_first, "page_reader", lambda: reader)
    monkeypatch.setattr(ocr_first, "pdf_frames", frames)
    monkeypatch.setattr(
        ocr_first, "scanned_pages", lambda _pdf: [True, True, True, True]
    )
    return pages


def scanned(n: int, kind: PageKind = PageKind.NO_TEXT) -> LayerPage:
    """A page with no text layer, as a scanner writes it."""
    return LayerPage(None, f"page {n} is {kind}", kind, 1)


def text_page(n: int) -> LayerPage:
    """A page of running text in the PDF's own text layer."""
    return LayerPage(f"Page {n} text.", None, PageKind.TEXT)


def layer_of(*pages: LayerPage) -> TextLayer:
    """The text layer of a file with these pages, as reading it leaves it."""
    return TextLayer(None, "page 1 is ocr:no-text", sum(p.images for p in pages), pages)


def test_a_scan_of_running_text_is_read_by_ocr_alone(ocr: dict[int, OcrPage]) -> None:
    """Every page stands, so Docling has nothing to read."""
    ocr.update({1: page(*prose()), 2: page(*prose())})

    reading = ocr_first.ocr_reading(Path("scan.pdf"), layer_of(scanned(1), scanned(2)))

    assert reading is not None
    assert reading.read == 2 and reading.docling == {}
    assert all("voted to adopt" in (p.text or "") for p in reading.layer.pages)


def test_a_table_page_of_a_scan_stays_with_ocr(ocr: dict[int, OcrPage]) -> None:
    """Its rows keep their cells together, and Docling is not asked."""
    ocr.update({1: page(*prose()), 2: page(*rows(), confidence=0.97)})

    reading = ocr_first.ocr_reading(Path("scan.pdf"), layer_of(scanned(1), scanned(2)))

    assert reading is not None
    assert reading.docling == {}
    assert "Item 3 1,300 2,350 3,375" in (reading.layer.pages[1].text or "")


def test_a_garbled_page_of_a_scan_goes_to_docling(ocr: dict[int, OcrPage]) -> None:
    """Only that page is left for Docling, in its place."""
    ocr.update(
        {1: page(*prose()), 2: page(*prose(), confidence=0.5), 3: page(*prose())}
    )

    reading = ocr_first.ocr_reading(
        Path("scan.pdf"), layer_of(scanned(1), scanned(2), scanned(3))
    )

    assert reading is not None
    assert reading.docling == {2: "page 2 is garbled"}
    assert reading.layer.pages[1].text is None


def test_a_mixed_pdf_keeps_its_text_pages_and_ocrs_the_rest(
    ocr: dict[int, OcrPage],
) -> None:
    """The text layer's pages stay as they were read."""
    ocr.update({2: page(*prose())})

    reading = ocr_first.ocr_reading(
        Path("mixed.pdf"), layer_of(text_page(1), scanned(2), text_page(3))
    )

    assert reading is not None
    assert [p.text is not None for p in reading.layer.pages] == [True, True, True]
    assert reading.layer.pages[0].text == "Page 1 text."


def test_a_scanner_layer_is_read_again(ocr: dict[int, OcrPage]) -> None:
    """A scanner's own invisible OCR is distrusted, as the text layer distrusts it."""
    ocr.update({1: page(*prose())})

    reading = ocr_first.ocr_reading(
        Path("scan.pdf"), layer_of(scanned(1, PageKind.SCANNER_LAYER))
    )

    assert reading is not None and reading.read == 1


def test_a_turned_scan_is_read_and_a_turned_text_page_is_not(
    ocr: dict[int, OcrPage], monkeypatch: pytest.MonkeyPatch
) -> None:
    """pdfium renders a turned page upright; a turned born-digital page stays Docling's."""
    monkeypatch.setattr(ocr_first, "scanned_pages", lambda _pdf: [True, False])
    turned = [
        LayerPage(None, f"page {n} is turned 90 degrees", None, 1) for n in (1, 2)
    ]
    ocr.update({1: page(*prose())})

    reading = ocr_first.ocr_reading(Path("turned.pdf"), layer_of(*turned))

    assert reading is not None
    assert reading.docling == {2: "page 2 is turned 90 degrees"}


def test_a_scan_ocr_cannot_stand_for_at_all_is_left_to_docling(
    ocr: dict[int, OcrPage],
) -> None:
    """Docling reads it whole, as before, and keeps its figures as it reads."""
    ocr.update({1: page(*prose(), confidence=0.5)})

    assert ocr_first.ocr_reading(Path("scan.pdf"), layer_of(scanned(1))) is None


def test_no_reader_or_a_failing_one_leaves_it_to_docling(
    ocr: dict[int, OcrPage], monkeypatch: pytest.MonkeyPatch
) -> None:
    """OCR-first never fails an ingest: Docling reads instead."""
    pages = layer_of(scanned(1))
    monkeypatch.setattr(ocr_first, "page_reader", lambda: None)
    assert ocr_first.ocr_reading(Path("scan.pdf"), pages) is None

    class Failing(StubReader):
        def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
            raise RuntimeError("onnxruntime could not run the detector")

    monkeypatch.setattr(ocr_first, "page_reader", lambda: Failing({}))
    assert ocr_first.ocr_reading(Path("scan.pdf"), pages) is None


def test_a_form_or_an_unreadable_pdf_is_left_to_docling(
    ocr: dict[int, OcrPage],
) -> None:
    """No pages in the layer: Docling reads the whole file, as before."""
    assert (
        ocr_first.ocr_reading(Path("form.pdf"), TextLayer(None, "a form field")) is None
    )


def test_a_turned_reading_must_read_as_text_to_replace_the_page() -> None:
    """A turn that reads as blank paper would drop the page's text unread."""
    readings = iter(
        [sideways(), page(line("ab", 300), ink=0.001), sideways(), sideways()]
    )
    reader = StubReader({})
    reader.read = lambda frames: ((f, next(readings)) for f in frames)  # type: ignore[method-assign]
    frame = Frame(1, Image.new("L", (40, 20), 0), 0.005)

    [(kept, read)] = list(read_upright(reader, [frame]))

    assert read.verdict() is PageVerdict.GARBLED
    assert kept.image.size == (40, 20)


def test_lines_standing_on_end_mean_a_page_read_sideways() -> None:
    """RapidOCR reads a quarter-turned page confidently, every line in one row."""
    assert page(*prose(), confidence=0.97).looks_sideways() is False
    tall = OcrPage(WIDTH, HEIGHT, tuple(prose()), 0.08, "en-US", 0.97, vertical=0.9)
    assert tall.looks_sideways()


def test_a_cover_keeps_its_own_title_over_ocrs_scraps(ocr: dict[int, OcrPage]) -> None:
    """With no page of running text, picture pages are read too; a reading of a
    few characters must not replace the title the layer had."""
    cover = LayerPage("Annual Report of the Harbour Board", None, PageKind.BIG_IMAGE, 1)
    ocr.update({1: page(line("Ann Rep", 300), ink=0.3), 2: page(*prose())})

    reading = ocr_first.ocr_reading(Path("cover.pdf"), layer_of(cover, scanned(2)))

    assert reading is not None
    assert reading.layer.pages[0].text == "Annual Report of the Harbour Board"


def test_blank_pages_alone_are_not_a_reading(ocr: dict[int, OcrPage]) -> None:
    """Every other page garbled: Docling reads the file whole, as before."""
    ocr.update({1: page(ink=0.001), 2: page(*prose(), confidence=0.5)})

    assert (
        ocr_first.ocr_reading(Path("scan.pdf"), layer_of(scanned(1), scanned(2)))
        is None
    )


def test_the_pdf_closes_when_ocr_fails_midway(
    ocr: dict[int, OcrPage], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Closed on the ingest thread, not by the garbage collector under pdfium's lock."""
    closed: list[bool] = []

    def frames(_original: Path, numbers: list[int], _max_side: int) -> Iterator[Frame]:
        try:
            for number in numbers:
                yield Frame(number, Image.new("L", (10, 10), 255), 0.0)
        finally:
            closed.append(True)

    class Failing(StubReader):
        def read(self, frames: Iterable[Frame]) -> Iterator[tuple[Frame, OcrPage]]:
            for frame in frames:
                if frame.number == 2:
                    raise RuntimeError("onnxruntime could not run the detector")
                yield frame, page(*prose())

    monkeypatch.setattr(ocr_first, "pdf_frames", frames)
    monkeypatch.setattr(ocr_first, "page_reader", lambda: Failing({}))

    assert (
        ocr_first.ocr_reading(Path("scan.pdf"), layer_of(*map(scanned, (1, 2, 3))))
        is None
    )
    assert closed == [True]


def test_a_resumed_reading_keeps_ocrs_pages(
    ocr: dict[int, OcrPage], tmp_path: Path
) -> None:
    """When Docling's part gives the queue up, the run that resumes does not read
    every page with OCR again; the same bytes and reader only."""
    original = tmp_path / "scan.pdf"
    original.write_bytes(b"%PDF scan")
    ocr.update({1: page(*prose()), 2: page(*prose(), confidence=0.5)})
    layer = layer_of(scanned(1), scanned(2))
    first = ocr_first.ocr_reading(original, layer)
    assert first is not None and first.kept == 0

    ocr.clear()  # any read now would fail
    second = ocr_first.ocr_reading(original, layer)

    assert second is not None and second.kept == 2
    assert second.docling == first.docling == {2: "page 2 is garbled"}
    assert second.layer.pages[0].text == first.layer.pages[0].text
    # Other bytes: nothing kept applies, and the stand-in, asked again, fails.
    original.write_bytes(b"%PDF another scan")
    assert ocr_first.ocr_reading(original, layer) is None


class Turn:
    """The ingest job's turn on the queue, past its minute with an upload
    waiting: it gives way at every check it is asked."""

    def __init__(self) -> None:
        self.gives_way = True
        self.cancelled = False

    def check_cancelled(self) -> None:
        if self.cancelled:
            raise JobCancelledError

    def give_way(self) -> None:
        if self.gives_way:
            raise JobYieldedError(PRIORITY_INTERACTIVE)


@pytest.fixture
def turn(monkeypatch: pytest.MonkeyPatch) -> Turn:
    """A reading inside an ingest job, whose turn this is."""
    made = Turn()
    monkeypatch.setattr(ocr_first, "object_session", lambda _document: object())
    monkeypatch.setattr(ocr_first, "reading_turn", lambda _session, _document: made)
    return made


def long_scan(
    folder: Path, ocr: dict[int, OcrPage], pages: int = 20
) -> tuple[Path, TextLayer]:
    """A scan of running text on disk, and its text layer."""
    original = folder / "scan.pdf"
    original.write_bytes(b"%PDF a long scan")
    ocr.update({n: page(*prose()) for n in range(1, pages + 1)})
    return original, layer_of(*map(scanned, range(1, pages + 1)))


def asked() -> list[int]:
    """The pages the stand-in reader has been asked for, in order."""
    reader = ocr_first.page_reader()
    assert isinstance(reader, StubReader)
    return reader.asked


def test_a_long_reading_gives_the_queue_up_with_its_pages_kept(
    ocr: dict[int, OcrPage], turn: Turn, tmp_path: Path
) -> None:
    """The run that resumes reads only the pages left, and comes to what one
    run would."""
    original, layer = long_scan(tmp_path, ocr)

    with pytest.raises(JobYieldedError):
        ocr_first.ocr_reading(original, layer, Document())
    assert asked() == list(range(1, 9))

    turn.gives_way = False
    resumed = ocr_first.ocr_reading(original, layer, Document())

    assert asked() == list(range(1, 21))
    assert resumed is not None and (resumed.kept, resumed.read) == (8, 20)
    forget_reading(original)
    straight = ocr_first.ocr_reading(original, layer)
    assert straight is not None and straight.kept == 0
    assert (resumed.layer, resumed.docling) == (straight.layer, straight.docling)


def test_a_reading_does_not_give_way_after_its_last_page(
    ocr: dict[int, OcrPage], turn: Turn, tmp_path: Path
) -> None:
    """Nothing is left to read; Docling's part, if any, gives way on its own."""
    original, layer = long_scan(tmp_path, ocr, pages=8)

    reading = ocr_first.ocr_reading(original, layer, Document())

    assert reading is not None and reading.read == 8


def test_a_reading_that_cannot_keep_its_pages_reads_on(
    ocr: dict[int, OcrPage], turn: Turn, tmp_path: Path
) -> None:
    """Giving way would lose every page read so far."""
    original, layer = long_scan(tmp_path, ocr)
    (tmp_path / "ocr").write_text("a file in the folder's place", "utf-8")

    reading = ocr_first.ocr_reading(original, layer, Document())

    assert reading is not None and reading.read == 20
    assert asked() == list(range(1, 21))


def test_a_cancelled_reading_forgets_the_pages_it_kept(
    ocr: dict[int, OcrPage], turn: Turn, tmp_path: Path
) -> None:
    """As a cancelled Docling reading drops its batches."""
    original, layer = long_scan(tmp_path, ocr)
    with pytest.raises(JobYieldedError):
        ocr_first.ocr_reading(original, layer, Document())
    assert (tmp_path / "ocr" / "pages.json").is_file()

    turn.cancelled = True
    with pytest.raises(JobCancelledError):
        ocr_first.ocr_reading(original, layer, Document())

    assert not (tmp_path / "ocr").exists()


def test_a_resumed_reading_with_no_page_of_text_is_docling_s_whole(
    ocr: dict[int, OcrPage], turn: Turn, tmp_path: Path
) -> None:
    """The pages kept before it gave way count, and are forgotten with the rest."""
    original, layer = long_scan(tmp_path, ocr)
    ocr.update({n: page(line("Fig.", 300), ink=0.2) for n in range(1, 9)})
    ocr.update({n: page(*prose(), confidence=0.5) for n in range(9, 21)})
    with pytest.raises(JobYieldedError):
        ocr_first.ocr_reading(original, layer, Document())

    turn.gives_way = False
    assert ocr_first.ocr_reading(original, layer, Document()) is None

    # An unsure page is read again turned, so pages 9 on are asked for more than once.
    assert asked()[:8] == list(range(1, 9))
    assert sorted(set(asked()[8:])) == list(range(9, 21))
    assert not (tmp_path / "ocr").exists()


@pytest.mark.parametrize("then", ["fails", "is turned off"])
def test_pages_kept_for_a_reading_docling_takes_over_are_forgotten(
    ocr: dict[int, OcrPage],
    turn: Turn,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    then: str,
) -> None:
    """Docling reads every page; a source left with ocr/ would look like a
    reading that gave way, and be given way to by no other."""
    original, layer = long_scan(tmp_path, ocr)
    with pytest.raises(JobYieldedError):
        ocr_first.ocr_reading(original, layer, Document())
    if then == "fails":
        ocr.clear()  # any read now fails
    else:
        monkeypatch.setattr(ocr_first, "page_reader", lambda: None)

    assert ocr_first.ocr_reading(original, layer, Document()) is None

    assert not (tmp_path / "ocr").exists()
