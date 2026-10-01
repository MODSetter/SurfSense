"""An uploaded image handed to Docling as the page it shows."""

import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from modules.documents.storage import UPLOAD_MIME_BY_SUFFIX

IMAGE_SUFFIXES = frozenset(
    suffix
    for suffix, mime in UPLOAD_MIME_BY_SUFFIX.items()
    if mime.startswith("image/")
)

# Docling renders pages for OCR at 3x its 72 dpi page unit.
OCR_DPI = 216
# Docling takes an image with no DPI as 72 dpi, so a phone photo became a page a
# yard tall and OCR upsampled it 3x. Read as an A4 page it renders near its own
# pixels: 7.9 s a page instead of 17.4 s, with the same text.
A4_HEIGHT_INCHES = 11.69


def as_page(path: Path) -> Any:
    """The image upright and sized as one page, as a stream Docling reads."""
    from docling.datamodel.base_models import DocumentStream

    with Image.open(path) as image:
        dpi = _page_dpi(image)
        frames = []
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            # Docling ignores EXIF, so a phone photo held sideways reads sideways.
            frames.append(ImageOps.exif_transpose(image).convert("RGB"))

    stream = io.BytesIO()
    frames[0].save(
        stream, "TIFF", dpi=(dpi, dpi), save_all=True, append_images=frames[1:]
    )
    stream.seek(0)
    return DocumentStream(name=f"{path.stem}.tiff", stream=stream)


def _page_dpi(image: Image.Image) -> float:
    # Never finer than the OCR render, never coarser than the file's own DPI, and
    # never below Docling's 72, which would upsample a small crop past 3x.
    declared = max(image.info.get("dpi") or (0,))
    as_a4 = max(image.size) / A4_HEIGHT_INCHES
    return max(72.0, float(declared), min(OCR_DPI, as_a4))
