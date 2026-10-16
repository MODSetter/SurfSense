"""Which pages of a PDF are scans, whose words only OCR can read.

A page is a scan when it shows no character from its text layer, an invisible
OCR layer included, or when raster images cover most of it, as on a scan
stamped with a digital page number.
"""

from pathlib import Path

import pypdfium2
import pypdfium2.raw as pdfium_c

from shared import pdfium

# How a scanner's OCR layer draws its words: present, but never shown.
_UNSHOWN = {pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE, pdfium_c.FPDF_TEXTRENDERMODE_CLIP}
# A born-digital cover photo counts too, which costs its page OCR's time but no
# figure.
_SCAN_RASTER_SHARE = 0.5


def scanned_pages(pdf: Path) -> list[bool] | None:
    """Whether each page is a scan; None for a file pdfium cannot read."""
    with pdfium.lock:
        try:
            document = pypdfium2.PdfDocument(pdf)
        except pypdfium2.PdfiumError:
            return None
        try:
            return [_is_scan(document, n) for n in range(len(document))]
        except pypdfium2.PdfiumError:
            return None
        finally:
            document.close()


def _is_scan(document: pypdfium2.PdfDocument, index: int) -> bool:
    page = document[index]
    try:
        return _raster_share(page) >= _SCAN_RASTER_SHARE or not _shows_text(page)
    finally:
        page.close()


def _shows_text(page: pypdfium2.PdfPage) -> bool:
    text = page.get_textpage()
    try:
        # Stops at the first one: a born-digital page shows it within a line.
        return any(_shown(text, n) for n in range(text.count_chars()))
    finally:
        text.close()


def _shown(text: pypdfium2.PdfTextPage, index: int) -> bool:
    character = chr(pdfium_c.FPDFText_GetUnicode(text, index))
    if not character.strip() or not character.isprintable():
        return False
    # None for a space or line break pdfium inserted between words.
    drawn_by = pdfium_c.FPDFText_GetTextObject(text, index)
    return (
        bool(drawn_by)
        and pdfium_c.FPDFTextObj_GetTextRenderMode(drawn_by) not in _UNSHOWN
    )


def _raster_share(page: pypdfium2.PdfPage) -> float:
    """How much of the page its images cover, overlaps counted twice."""
    left, bottom, right, top = page.get_bbox()
    covered = 0.0
    for image in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        box = image.get_bounds()
        # Bounds inside a form XObject are in the form's space, not the page's.
        holder = image.container
        while holder is not None:
            box = holder.get_matrix().on_rect(*box)
            holder = holder.container
        width = min(box[2], right) - max(box[0], left)
        height = min(box[3], top) - max(box[1], bottom)
        covered += max(width, 0.0) * max(height, 0.0)
    return covered / max((right - left) * (top - bottom), 1.0)
