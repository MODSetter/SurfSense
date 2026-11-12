"""Binding a comic's pictures into one PDF: by page or as one scroll, in its reading direction."""

import io

import pytest
from PIL import Image
from pypdf import PdfReader

from worker.studio.media.visual.comic_binding.bind import (
    MARGIN,
    WIDTH,
    BoundPage,
    _wrapped,
    bind,
)

pytestmark = pytest.mark.unit

POINTS_WIDE = 6.625 * 72


def _png(width: int, height: int, colour: str = "teal") -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(out, "PNG")
    return out.getvalue()


def _sizes(pdf: bytes) -> list[tuple[float, float]]:
    return [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in PdfReader(io.BytesIO(pdf)).pages
    ]


def test_each_picture_is_a_page_at_comic_book_width_as_tall_as_its_picture() -> None:
    """No picture is cropped or letterboxed to fit a paper size."""
    pdf = bind(
        "The Lighthouse Cat",
        [BoundPage(_png(400, 600)), BoundPage(_png(400, 600, "navy"))],
        layout="pages",
        direction="ltr",
    )

    assert _sizes(pdf) == [(POINTS_WIDE, POINTS_WIDE * 1.5)] * 2
    assert PdfReader(io.BytesIO(pdf)).metadata.title == "The Lighthouse Cat"


def test_a_pages_lines_are_set_under_it_exactly() -> None:
    """For a misspelt page, or one drawn without words, the strip carries its text."""
    pdf = bind(
        "Cat",
        [BoundPage(_png(400, 400), ("NORA: The bulb is broken!",))],
        layout="pages",
        direction="ltr",
    )

    ((width, height),) = _sizes(pdf)
    assert height > width
    assert (
        "NORA: The bulb is broken!"
        in PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    )


def test_a_webtoon_scrolls_down_one_long_page() -> None:
    """Its beats stack in one column, read by scrolling, not page by page."""
    pdf = bind(
        "Beats",
        [BoundPage(_png(400, 600)) for _ in range(3)],
        layout="scroll",
        direction="ltr",
    )

    ((_, height),) = _sizes(pdf)
    assert height > 3 * POINTS_WIDE * 1.5


def test_a_long_scroll_starts_a_new_page_every_twelve() -> None:
    """No viewer meets one page tall enough to fail."""
    pdf = bind(
        "Beats",
        [BoundPage(_png(40, 60)) for _ in range(13)],
        layout="scroll",
        direction="ltr",
    )

    assert len(_sizes(pdf)) == 2


def test_a_manga_tells_its_reader_it_reads_right_to_left() -> None:
    """A reader then lays its spreads out as a manga's are."""
    pdf = bind("Manga", [BoundPage(_png(400, 600))], layout="pages", direction="rtl")

    preferences = PdfReader(io.BytesIO(pdf)).trailer["/Root"]["/ViewerPreferences"]
    assert preferences["/Direction"] == "/R2L"


def test_pages_are_placed_as_jpeg_so_a_book_stays_small() -> None:
    """Four PNG pages made 10 to 28 MB in the spike."""
    noisy = Image.effect_noise((800, 1200), 64).convert("RGB")
    out = io.BytesIO()
    noisy.save(out, "PNG")

    pdf = bind("Noise", [BoundPage(out.getvalue())], layout="pages", direction="ltr")

    assert len(pdf) < len(out.getvalue())


def _fonts(pdf: bytes) -> set[str]:
    page = PdfReader(io.BytesIO(pdf)).pages[0]
    return {str(font["/BaseFont"]) for font in page["/Resources"]["/Font"].values()}


def test_a_mangas_japanese_lines_are_set_in_a_font_that_has_them() -> None:
    """Helvetica draws a box for every kana and kanji."""
    pdf = bind(
        "猫",
        [BoundPage(_png(400, 400), ("ノラ: 電球が壊れた!",))],
        layout="pages",
        direction="rtl",
    )

    assert "/HeiseiKakuGo-W5" in _fonts(pdf)


def test_a_line_with_no_spaces_wraps_inside_the_page() -> None:
    """Japanese and Chinese have no spaces to break at; the strip grows instead."""
    short = bind(
        "猫", [BoundPage(_png(400, 400), ("猫",))], layout="pages", direction="rtl"
    )
    long = bind(
        "猫",
        [BoundPage(_png(400, 400), ("猫" * 200,))],
        layout="pages",
        direction="rtl",
    )

    assert _sizes(long)[0][1] > _sizes(short)[0][1]


def test_a_word_too_wide_is_cut_with_no_spaces_added() -> None:
    """Letters of a cut word join as written; a real space between words stays."""
    line = "電球" * 60 + " 猫"

    wrapped = _wrapped(line, WIDTH - 2 * MARGIN)

    assert len(wrapped) > 1
    # No space is added inside the cut word; the break takes the real one's place.
    assert " " not in "".join(wrapped[:-1])
    assert "".join(wrapped).replace(" ", "") == line.replace(" ", "")
