"""Pages as greyscale pictures for OCR: a PDF's pages rendered, an image's frames.

216 dpi, the resolution Docling OCRs at: 144 dpi lost table numbers, and 300 dpi
read nothing more on real forms, 1.5x slower.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import pypdfium2
from PIL import Image, ImageOps

from shared import pdfium
from worker.ingestion.image_page import A4_HEIGHT_INCHES, OCR_DPI

# Darker than this counts as ink, for telling blank paper from an unread page.
_INK_LEVEL = 128


@dataclass(frozen=True)
class Frame:
    """Page `number`, counted from 1, as an 8-bit greyscale picture."""

    number: int
    image: Image.Image
    ink: float


def pdf_frames(original: Path, pages: Sequence[int], max_side: int) -> Iterator[Frame]:
    """The pages rendered upright (pdfium applies /Rotate), holding pdfium's lock
    only while it renders, so the system's OCR reads one page as the next renders."""
    with pdfium.lock:
        pdf = pypdfium2.PdfDocument(original)
    try:
        for number in pages:
            with pdfium.lock:
                page = pdf[number - 1]
                try:
                    width, height = page.get_size()
                    scale = min(OCR_DPI / 72, max_side / max(width, height, 1) * 0.999)
                    bitmap = page.render(scale=scale, grayscale=True)
                    try:
                        image = bitmap.to_pil().convert("L")
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            yield Frame(number, image, _ink(image))
    finally:
        with pdfium.lock:
            pdf.close()


def image_frames(path: Path, max_side: int) -> Iterator[Frame]:
    """Each frame upright by its EXIF and sized as an A4 page at 216 dpi, never
    below its own pixels, as Docling's image page is: real 754x1000 forms gave
    Windows OCR 0.49 of their words at their own size and 0.61 at A4 size."""
    with Image.open(path) as image:
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            frame = ImageOps.exif_transpose(image).convert("L")
            longest = max(frame.size)
            scale = min(
                max(1.0, OCR_DPI * A4_HEIGHT_INCHES / longest), max_side / longest
            )
            if abs(scale - 1.0) > 0.01:
                size = (round(frame.width * scale), round(frame.height * scale))
                frame = frame.resize(size, Image.Resampling.LANCZOS)
            yield Frame(index + 1, frame, _ink(frame))


def _ink(image: Image.Image) -> float:
    histogram = image.histogram()
    return sum(histogram[:_INK_LEVEL]) / max(1, image.width * image.height)
