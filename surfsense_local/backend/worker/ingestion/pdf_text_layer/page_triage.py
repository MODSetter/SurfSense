"""Whether one page's text layer is its text: round 1's pdfium triage. Of 570 Boston
budget pages it flags 8, each a full-page image; of 61 spec and live-run pages, none.

The garble ratios and the leader collapse are marker's (Apache-2.0, detect_bad_ocr);
an invisible layer over a scan is how OCRmyPDF spots a scanner's OCR.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import pypdfium2.raw as pdfium_c

from worker.ingestion.pdf_text_layer.printable_text import printable

# Fewer non-space characters than this is a sparse page, or a cover's title.
SPARSE_CHARS = 20
# A page with less text whose images cover more of it than this is a scan.
SCAN_IMAGE_COVER = 0.05
# An invisible layer over images covering more than this is a scanner's OCR.
SCANNER_LAYER_COVER = 0.5
# Beyond this share, an image is the page; its text is a cover's title or a caption.
BIG_IMAGE_COVER = 0.65
# Below this share of letters and digits, the text is garbage, as in marker.
GARBLED_ALNUM = 0.3
# Rules, a frame and crop marks stay under this; one outlined word already passes it.
BLANK_PAGE_SEGMENTS = 40
# Live text only this near the top or bottom edge is a stamp, a running header or a
# page number: over a scan or outlined lettering, the page's text is not live. Of
# 648 corpus and stress pages, it sends one to OCR: a raster org chart.
MARGIN_BAND = 0.12

# Table-of-contents dot leaders and form underscores are typography, not garbage.
_LEADERS = re.compile(r"(?:[.·•…_\-]\s*){3,}")
_SPACE = re.compile(r"\s+")

Box = tuple[float, float, float, float]  # left, bottom, right, top


class PageKind(StrEnum):
    TEXT = "ok:text"
    SPARSE = "ok:sparse"
    BLANK = "ok:blank"
    BIG_IMAGE = "mixed:big-image"
    NO_TEXT = "ocr:no-text"
    SCANNER_LAYER = "ocr-layer:scanner"
    GARBLED = "ocr:garbled"


# A full-page image with a title over it is a section cover: Docling's OCR of
# the photo added 0-11 words of noise there.
TEXT_USABLE = frozenset(
    {PageKind.TEXT, PageKind.SPARSE, PageKind.BLANK, PageKind.BIG_IMAGE}
)


@dataclass(frozen=True)
class PageReading:
    text: str  # line breaks as "\n"
    kind: PageKind
    images: int  # image objects, at any depth


@dataclass(frozen=True)
class _Signs:
    chars: int
    unmapped: int
    bad: int
    alnum: float
    image_cover: float
    images: int
    text_objects: int
    invisible: int
    margins_only: bool


def read_page(page: Any) -> PageReading:
    """The page's text and what kind of page it is. Hold shared.pdfium.lock."""
    # The page's visible box: its origin need not be 0,0.
    box = page.get_bbox()
    textpage = page.get_textpage()
    try:
        count = textpage.count_chars()
        text = textpage.get_text_range() if count > 0 else ""
        unmapped = sum(
            pdfium_c.FPDFText_HasUnicodeMapError(textpage, index) == 1
            for index in range(count)
        )
        margins_only = _in_margins_only(textpage, count, box)
    finally:
        textpage.close()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    signs = _signs(page, box, text, unmapped, margins_only)
    return PageReading(printable(text), _kind(page, signs), signs.images)


def _signs(page: Any, box: Box, text: str, unmapped: int, margins_only: bool) -> _Signs:
    left, bottom, right, top = box
    area = max(1.0, (right - left) * (top - bottom))
    image_area = 0.0
    images = text_objects = invisible = 0
    # Every depth: N-up imposition and a PDF included in a PDF nest Form XObjects.
    for obj in page.get_objects(
        filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE, pdfium_c.FPDF_PAGEOBJ_TEXT]
    ):
        if obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            x0, y0, x1, y1 = _on_page(obj)
            images += 1
            image_area += max(0, min(x1, right) - max(x0, left)) * max(
                0, min(y1, top) - max(y0, bottom)
            )
        else:
            text_objects += 1
            mode = pdfium_c.FPDFTextObj_GetTextRenderMode(obj.raw)
            if mode == pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE:
                invisible += 1
    return _Signs(
        chars=len(_SPACE.sub("", text)),
        unmapped=unmapped,
        bad=sum(map(_is_bad, text)),
        alnum=_alnum_ratio(text),
        image_cover=min(1.0, image_area / area),
        images=images,
        text_objects=text_objects,
        invisible=invisible,
        margins_only=margins_only,
    )


def _kind(page: Any, signs: _Signs) -> PageKind:
    if signs.chars < SPARSE_CHARS and signs.image_cover > SCAN_IMAGE_COVER:
        return PageKind.NO_TEXT
    if signs.chars == 0:
        # Triage sent every textless page to OCR; a blank one has nothing to read.
        blank = signs.images == 0 and _barely_drawn(page)
        return PageKind.BLANK if blank else PageKind.NO_TEXT
    if signs.margins_only and (
        signs.image_cover > SCAN_IMAGE_COVER or not _barely_drawn(page)
    ):
        return PageKind.NO_TEXT
    if signs.chars < SPARSE_CHARS:
        return PageKind.SPARSE
    if (
        signs.invisible
        and signs.invisible >= 0.5 * signs.text_objects
        and signs.image_cover > SCANNER_LAYER_COVER
    ):
        return PageKind.SCANNER_LAYER
    garbage = max(6, 0.03 * signs.chars)
    if signs.unmapped > garbage or signs.bad > garbage or signs.alnum < GARBLED_ALNUM:
        return PageKind.GARBLED
    if signs.image_cover > BIG_IMAGE_COVER:
        return PageKind.BIG_IMAGE
    return PageKind.TEXT


def _in_margins_only(textpage: Any, count: int, box: Box) -> bool:
    """Whether every character lies in the page's top or bottom band; a body line
    ends the search, so a page of text costs a few lookups."""
    _, bottom, _, top = box
    band = MARGIN_BAND * (top - bottom)
    found = False
    for index in range(count):
        left, low, right, high = textpage.get_charbox(index)
        if right <= left:
            continue  # a space or line break pdfium added, with no box of its own
        if low < top - band and high > bottom + band:
            return False
        found = True
    return found


def _on_page(obj: Any) -> Box:
    # pdfium gives an object's bounds in its form's space; each form's matrix maps
    # them into the space it is drawn in.
    bounds = obj.get_bounds()
    form = obj.container
    while form is not None:
        bounds = form.get_matrix().on_rect(*bounds)
        form = form.container
    return bounds


def _barely_drawn(page: Any) -> bool:
    """Drawn shapes too few to be lettering, which Docling's OCR reads off them."""
    segments = 0
    for path in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_PATH]):
        segments += max(0, pdfium_c.FPDFPath_CountSegments(path.raw))
        if segments > BLANK_PAGE_SEGMENTS:
            return False
    return True


def _is_bad(char: str) -> bool:
    """A character no font maps to text: U+FFFD, private use, or a control code."""
    code = ord(char)
    return (
        code == 0xFFFD
        or 0xE000 <= code <= 0xF8FF
        or (code < 0x20 and char not in "\r\n\t")
    )


def _alnum_ratio(text: str) -> float:
    letters = _LEADERS.sub(" ", text).replace(" ", "").replace("\n", "")
    return 1.0 if not letters else sum(c.isalnum() for c in letters) / len(letters)
