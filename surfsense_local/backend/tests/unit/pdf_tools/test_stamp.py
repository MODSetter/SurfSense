"""Stamping text on a copy: a watermark, page numbers, a header or a footer."""

import pypdfium2
import pytest
from reportlab.lib.pagesizes import A4

from modules.pdf_tools import stamp_font
from modules.pdf_tools.opened_pdf import open_pdf
from modules.pdf_tools.page_operations import rotate
from modules.pdf_tools.refusal import PdfRefusedError
from modules.pdf_tools.stamp import stamp
from tests.unit.pdf_tools.pdfs import drawn_texts, heavy, numbered, texts

pytestmark = pytest.mark.unit


def _shown(data: bytes, page: int, words: str) -> list[tuple[float, float]]:
    """Where each run of `words` lands as the page is shown, rotation applied, from
    its bottom left: the centre of its box across, the bottom of it up.

    Drawn by pdfium, so text inside a form XObject is placed as a viewer places it.
    """
    pdf = pypdfium2.PdfDocument(data)
    try:
        shown = pdf[page - 1]
        left, bottom, right, top = shown.get_cropbox()
        width, height = right - left, top - bottom
        turn = shown.get_rotation() % 360
        text = shown.get_textpage()
        searcher = text.search(words)
        found: list[tuple[float, float]] = []
        while (hit := searcher.get_next()) is not None:
            first, count = hit
            corners = []
            for index in range(first, first + count):
                x0, y0, x1, y1 = text.get_charbox(index)
                for x, y in ((x0, y0), (x1, y1)):
                    x, y = x - left, y - bottom
                    corners.append(
                        {
                            0: (x, y),
                            90: (y, width - x),
                            180: (width - x, height - y),
                            270: (height - y, x),
                        }[turn]
                    )
            xs, ys = [c[0] for c in corners], [c[1] for c in corners]
            found.append(((min(xs) + max(xs)) / 2, min(ys)))
        return found
    finally:
        pdf.close()


def test_page_numbers_go_on_every_page_named() -> None:
    """{page} is the page's own number, {total} the count."""
    reader = open_pdf(numbered(3), "a")

    stamped = stamp(reader, "page_numbers", "{page} of {total}", None, [2, 3])

    pages = texts(stamped)
    assert "of 3" not in pages[0]
    assert "2 of 3" in pages[1]
    assert "3 of 3" in pages[2]


def test_page_numbers_default_to_the_bottom_centre() -> None:
    """Where most documents carry them."""
    stamped = stamp(open_pdf(numbered(1), "a"), "page_numbers", None, None, [1])

    (x, y), *_ = _shown(stamped, 1, "1 / 1")
    width, _ = A4
    assert y < 60
    assert abs(x - width / 2) < 30


def test_page_number_text_without_the_page_is_refused() -> None:
    """Text without {page} would print the same words on every page."""
    with pytest.raises(PdfRefusedError, match=r"\{page\}"):
        stamp(open_pdf(numbered(1), "a"), "page_numbers", "Draft", None, [1])


def test_a_header_goes_at_the_top_where_asked() -> None:
    """position places the line."""
    stamped = stamp(open_pdf(numbered(1), "a"), "header", "ACME Ltd", "top-right", [1])

    ((x, y),) = _shown(stamped, 1, "ACME Ltd")
    width, height = A4
    assert y > height - 60
    assert x > width / 2


def test_a_watermark_is_drawn_and_the_text_kept() -> None:
    """The watermark is added; the page's own text stays."""
    stamped = stamp(
        open_pdf(numbered(2), "a"), "watermark", "CONFIDENTIAL", None, [1, 2]
    )

    assert all("CONFIDENTIAL" in page for page in texts(stamped))
    assert all("Page" in page for page in texts(stamped))


def test_a_footer_sits_at_the_bottom_of_a_page_shown_turned() -> None:
    """The page stays turned, and the footer lands at the bottom as the reader sees it."""
    turned = open_pdf(rotate(open_pdf(numbered(1), "a"), [1], 90), "a")

    stamped = stamp(turned, "footer", "Footer here", None, [1])

    ((x, y),) = _shown(stamped, 1, "Footer here")
    shown_width, _ = A4[1], A4[0]
    assert y < 60
    assert abs(x - shown_width / 2) < 60


def test_a_kind_without_text_is_refused() -> None:
    """Only page numbers have text of their own."""
    with pytest.raises(PdfRefusedError, match="Give the text"):
        stamp(open_pdf(numbered(1), "a"), "watermark", "  ", None, [1])


def test_text_no_font_on_this_computer_can_write_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Helvetica has no Cyrillic; without a system font the text would print as boxes."""
    monkeypatch.setattr(stamp_font, "_candidates", lambda: [])

    with pytest.raises(PdfRefusedError, match="no font"):
        stamp(open_pdf(numbered(1), "a"), "watermark", "Черновик", None, [1])


def test_text_beyond_latin_uses_a_font_from_this_computer() -> None:
    """Non-Latin text is embedded from a system font."""
    if stamp_font.font_for("Черновик") is None:
        pytest.skip("this computer has no font with Cyrillic letters")

    stamped = stamp(open_pdf(numbered(1), "a"), "footer", "Черновик", None, [1])

    assert "Черновик" in texts(stamped)[0]


def test_a_stamp_keeps_each_pages_own_content_as_stored() -> None:
    """A page's content is never decoded: a few KB that decode to megabytes on
    every page would otherwise fill memory and the new file."""
    reader = open_pdf(heavy(numbered(20), 4 * 1024 * 1024), "a")

    stamped = stamp(reader, "footer", "Draft", None, list(range(1, 21)))

    assert len(stamped) < 1024 * 1024
    pages = drawn_texts(stamped)
    assert all("Draft" in page for page in pages)
    assert all(f"Page {n}" in page for n, page in enumerate(pages, 1))


@pytest.mark.parametrize("text", ["\u200b", "\u200b\u0301"])
def test_text_with_nothing_to_draw_is_refused(text: str) -> None:
    """Characters with no width cannot be fitted to the page; refused in a sentence."""
    if stamp_font.font_for(text) is None:
        pytest.skip("this computer has no font with zero-width characters")
    for kind in ("watermark", "footer"):
        with pytest.raises(PdfRefusedError, match="nothing to draw"):
            stamp(open_pdf(numbered(1), "a"), kind, text, None, [1])
