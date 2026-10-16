"""Which pages of a PDF Docling reads, how its markdown joins the text layer's,
and which text-read PDFs get the figures-only pass queued at idle."""

import pytest

from worker.ingestion.docling_batches.page_runs import PageRun
from worker.ingestion.figures.idle_pass import IDLE_PASS_PAGES, wants_idle_pass
from worker.ingestion.pdf_reading.docling_pages import pages_for_docling
from worker.ingestion.pdf_reading.spliced_text import spliced
from worker.ingestion.pdf_text_layer import LayerPage, TextLayer
from worker.ingestion.pdf_text_layer.page_triage import PageKind

pytestmark = pytest.mark.unit


def text(n: int, segments: int = 0, images: int = 0) -> LayerPage:
    """A page of running text."""
    return LayerPage(f"Page {n} text.", None, PageKind.TEXT, images, segments)


def flagged(n: int) -> LayerPage:
    """A page only Docling can read."""
    return LayerPage(None, f"page {n} is ocr:no-text", PageKind.NO_TEXT, 1)


def layer(*pages: LayerPage) -> TextLayer:
    """The text layer of a file with these pages, as reading it leaves it."""
    images = sum(page.images for page in pages)
    refused = next((page for page in pages if page.text is None), None)
    if refused is not None:
        return TextLayer(None, refused.refused_because, images, pages)
    text = "\n\n".join(page.text or "" for page in pages)
    return TextLayer(text, None, images, pages)


def test_runs_of_flagged_pages_go_to_docling() -> None:
    """Each run of consecutive pages is one reading; the pages between stay text."""
    pages = layer(flagged(1), text(2), flagged(3), flagged(4), text(5), text(6))

    assert pages_for_docling(pages) == [PageRun(1, 1), PageRun(3, 4)]


def test_more_than_half_flagged_is_a_scan_docling_reads_whole() -> None:
    """Half is still spliced."""
    assert pages_for_docling(layer(flagged(1), flagged(2), text(3))) is None
    assert pages_for_docling(layer(flagged(1), text(2))) == [PageRun(1, 1)]


def test_a_file_with_no_page_named_goes_to_docling_whole() -> None:
    """A filled form, a file pdfium cannot read, or the switch off."""
    assert pages_for_docling(TextLayer(None, "a form field holds an answer")) is None


def test_flagged_pages_beside_covers_alone_go_to_docling_whole() -> None:
    """With no running text among the rest, the content is in the pixels."""
    sparse = LayerPage("Appendix B", None, PageKind.SPARSE)

    assert pages_for_docling(layer(flagged(1), sparse, sparse)) is None


def test_docling_markdown_takes_its_pages_place_a_blank_line_apart() -> None:
    """As a text-read PDF's pages are joined."""
    pages = layer(flagged(1), text(2), flagged(3), flagged(4), text(5))

    joined = spliced(pages, [(PageRun(1, 1), "# Cover"), (PageRun(3, 4), "| a | b |")])

    assert joined == "# Cover\n\nPage 2 text.\n\n| a | b |\n\nPage 5 text."


def test_the_idle_pass_is_for_image_objects_and_never_a_long_file() -> None:
    """Drawing alone waits to be asked: no segment count told a chart from a
    table's rules."""
    assert wants_idle_pass(layer(text(1), text(2, images=1)))
    assert not wants_idle_pass(layer(text(1, segments=1128), text(2)))
    at_most = [text(n, images=1) for n in range(1, IDLE_PASS_PAGES + 1)]
    assert wants_idle_pass(TextLayer("text", images=40, pages=tuple(at_most)))
    long_file = [text(n, images=1) for n in range(1, IDLE_PASS_PAGES + 2)]
    assert not wants_idle_pass(TextLayer("text", images=99, pages=tuple(long_file)))
