"""RapidOCR itself, on every system CI runs: it reads a rendered page, keeps a
table's rows on their lines, and turns a page it was handed sideways upright.

Its models ship in the rapidocr wheel, so no pack is needed here.
"""

from collections.abc import Iterator

import pytest
from PIL import Image, ImageDraw, ImageFont

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.page import PageVerdict
from worker.ingestion.scan_ocr.rapid import RapidOcr
from worker.ingestion.scan_ocr.upright import read_upright

pytestmark = pytest.mark.integration

_FONTS = (
    "arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
PROSE = [
    "The harbour board met on Tuesday to agree the budget",
    "for the coming year and the plan for the new quay.",
    "Members asked for the figures to be published in full",
    "before the next meeting of the board in the spring.",
]
ROWS = [("Fuel", "1,250"), ("Wages", "8,400"), ("Repairs", "2,075")]


def font(size: int = 40) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """A scalable font, so the text is large enough to read; Pillow's own as a last resort."""
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def a_page() -> Image.Image:
    """Prose, then a small table whose labels and amounts stand far apart."""
    image = Image.new("L", (1700, 1100), 255)
    draw = ImageDraw.Draw(image)
    for n, text in enumerate(PROSE):
        draw.text((120, 120 + 70 * n), text, fill=0, font=font())
    for n, (label, amount) in enumerate(ROWS):
        draw.text((120, 520 + 70 * n), label, fill=0, font=font())
        draw.text((1200, 520 + 70 * n), amount, fill=0, font=font())
    return image


@pytest.fixture(scope="module")
def rapid() -> Iterator[RapidOcr]:
    """RapidOCR built once for the module, with the wheel's models when no pack is here."""
    reader = RapidOcr.create()
    if reader is None:
        pytest.skip("rapidocr is not installed")
    yield reader


def test_rapidocr_reads_a_page_and_keeps_a_rows_cells_together(rapid: RapidOcr) -> None:
    """A row's label and amount, far apart on the page, read as one line."""
    [(_, page)] = list(rapid.read([Frame(1, a_page(), 0.05)]))
    text = page.text()

    assert page.verdict() is PageVerdict.TEXT
    assert page.confidence is not None and page.confidence > 0.8
    assert "harbour board met on Tuesday" in text
    assert any("Wages" in line and "8,400" in line for line in text.splitlines())


def test_a_page_handed_over_sideways_is_read_upright(rapid: RapidOcr) -> None:
    """The engine is unsure of a sideways page, so it is read again turned."""
    sideways = a_page().rotate(90, expand=True)

    [(frame, page)] = list(read_upright(rapid, [Frame(1, sideways, 0.05)]))

    assert page.verdict() is not PageVerdict.GARBLED
    assert "harbour board" in page.text()
    assert frame.image.size == (1700, 1100)
