"""A PDF picture's pixels: its region of the page, rendered on its own after conversion.

Not Docling's generate_picture_images: that keeps every page's render, at 1x
and at the crop scale, until the conversion ends, about 7 MiB a page even on
pages with no picture (574 MiB for 80 A4 pages).
"""

import logging
from pathlib import Path
from typing import Any

import pypdfium2
from PIL import Image

logger = logging.getLogger(__name__)

# 144 dpi: sharp enough to place a figure at a page's width.
CROP_SCALE = 2.0


class PdfPictureCrops:
    """The original PDF, open while its pictures are cropped one at a time."""

    def __init__(self, original: Path) -> None:
        self._pdf = pypdfium2.PdfDocument(original)

    def close(self) -> None:
        self._pdf.close()

    def pixels(self, item: Any) -> Image.Image | None:
        """The picture's region at CROP_SCALE, or None when it has no place on a page."""
        if not item.prov:
            return None
        place = item.prov[0]
        if not 1 <= place.page_no <= len(self._pdf):
            return None
        page = self._pdf[place.page_no - 1]
        try:
            return _render_region(page, place.bbox)
        except (pypdfium2.PdfiumError, ValueError) as failure:
            logger.warning("skipped a picture that does not render: %s", failure)
            return None
        finally:
            page.close()


def _render_region(page: Any, bbox: Any) -> Image.Image | None:
    # Docling measures the page as pdfium does, so its box maps onto it directly;
    # render() takes how much to cut off each edge, from the bottom-left.
    width, height = page.get_size()
    box = bbox.to_bottom_left_origin(page_height=height)
    left, bottom = max(box.l, 0.0), max(box.b, 0.0)
    right, top = min(box.r, width), min(box.t, height)
    if right - left < 1 or top - bottom < 1:
        return None
    bitmap = page.render(
        scale=CROP_SCALE, crop=(left, bottom, width - right, height - top)
    )
    try:
        # A copy: the bitmap's buffer is freed when it closes.
        return bitmap.to_pil().copy()
    finally:
        bitmap.close()
