"""The pictures a source offers as figures, in the order it shows them."""

import hashlib
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple

from PIL import Image, ImageOps

from worker.ingestion.figures.pdf_crops import PdfPictureCrops
from worker.ingestion.image_page import IMAGE_SUFFIXES

logger = logging.getLogger(__name__)


class Picture(NamedTuple):
    image: Image.Image  # RGB, or RGBA when it has transparency: what PNG holds
    caption: str | None
    page: int | None


def pictures_in(original: Path, converted: Any) -> Iterator[Picture]:
    """An image file is its own one picture; any other file, Docling's pictures in it.

    A PDF's pictures are cropped from its pages; a Word or PowerPoint file's
    are the pixels it embeds. A picture repeated with the same pixels, like a
    letterhead logo on every page, is offered once.
    """
    suffix = original.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        found = iter([_whole_image(original)])
    elif suffix == ".pdf":
        found = _pdf_pictures(original, converted)
    else:
        found = _docling_pictures(converted, _embedded_pixels)
    seen: set[bytes] = set()
    for picture in found:
        fingerprint = _fingerprint(picture.image)
        if fingerprint not in seen:
            seen.add(fingerprint)
            yield picture


def _whole_image(path: Path) -> Picture:
    with Image.open(path) as image:
        # Upright as it displays: a phone photo held sideways is stored on its side.
        upright = ImageOps.exif_transpose(image)
    return Picture(_png_ready(upright), None, None)


def _pdf_pictures(original: Path, document: Any) -> Iterator[Picture]:
    crops = PdfPictureCrops(original)
    try:
        yield from _docling_pictures(document, crops.pixels)
    finally:
        crops.close()


def _docling_pictures(
    document: Any, pixels_of: Callable[[Any], Image.Image | None]
) -> Iterator[Picture]:
    from docling_core.types.doc import ContentLayer, PictureItem

    # Furniture too: a logo in a letterhead is the picture a user asks for.
    layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
    for item, _level in document.iterate_items(included_content_layers=layers):
        if not isinstance(item, PictureItem):
            continue
        image = pixels_of(item)
        if image is None:
            continue
        yield Picture(
            _png_ready(image),
            item.caption_text(document) or None,
            item.prov[0].page_no if item.prov else None,
        )


def _embedded_pixels(item: Any) -> Image.Image | None:
    """The pixels the file itself carries, or None.

    Never a picture that refers to a path: an uploaded page could otherwise
    pull any image on this machine into the user's documents.
    """
    reference = item.image
    if reference is None or isinstance(reference.uri, Path):
        return None
    if reference.uri.scheme != "data":
        return None
    try:
        image = reference.pil_image
        image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as failure:
        logger.warning("skipped a picture that does not decode: %s", failure)
        return None
    return image


def _png_ready(image: Image.Image) -> Image.Image:
    # PNG cannot hold CMYK, and python-docx and ReportLab read RGB(A) PNGs alike.
    return image.convert("RGBA" if image.has_transparency_data else "RGB")


def _fingerprint(image: Image.Image) -> bytes:
    shape = f"{image.mode}{image.size}".encode()
    return hashlib.sha256(shape + image.tobytes()).digest()
