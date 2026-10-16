"""A PDF's text layer as its text, page by page: a page Docling must read is
named, so the rest of the file can still come from its own text."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from shared import pdfium
from worker.ingestion.pdf_text_layer.filled_fields import holds_filled_fields
from worker.ingestion.pdf_text_layer.page_triage import (
    TEXT_USABLE,
    PageKind,
    drawn_objects,
    read_page,
)
from worker.ingestion.pdf_text_layer.switch import text_layer_on

logger = logging.getLogger(__name__)

# The answer-quality A/B measured pages joined this way (0.70 vs Docling's 0.62).
PAGE_BREAK = "\n\n"


@dataclass(frozen=True)
class LayerPage:
    """One page's own text, or None and why only Docling reads it."""

    text: str | None
    refused_because: str | None = None
    kind: PageKind | None = None
    images: int = 0
    segments: int = 0


@dataclass(frozen=True)
class TextLayer:
    """The PDF's own text, or None and why Docling must read the file."""

    text: str | None
    refused_because: str | None = None
    # Image objects on its pages: with none, Docling would find few figures.
    images: int = 0
    # Every page's reading; empty when Docling must read the whole file anyway.
    pages: tuple[LayerPage, ...] = ()


def read_text_layer(original: Path) -> TextLayer:
    """Never raises: whatever goes wrong here, Docling can still read the file."""
    if not text_layer_on():
        return TextLayer(None, "SURFSENSE_LOCAL_PDF_TEXT_LAYER is off")
    try:
        with pdfium.lock:
            return _read(original)
    except Exception as failure:  # Docling reads it, as before the text layer
        logger.warning("could not read the text layer of %s", original, exc_info=True)
        return TextLayer(None, f"pdfium could not read it: {failure}")


def _read(original: Path) -> TextLayer:
    pdf = pypdfium2.PdfDocument(original)
    try:
        if holds_filled_fields(pdf):
            return TextLayer(None, "a form field holds an answer")
        pages = tuple(_page(pdf, index) for index in range(len(pdf)))
    finally:
        pdf.close()
    images = sum(page.images for page in pages)
    refused = next((page for page in pages if page.text is None), None)
    if refused is not None:
        return TextLayer(None, refused.refused_because, images, pages)
    text = PAGE_BREAK.join(page.text or "" for page in pages)
    if not text.strip():
        return TextLayer(None, "it has no text layer", images, pages)
    # Covers, titles and stamps alone: whatever else the pages say, only OCR reads.
    if not any(page.kind is PageKind.TEXT for page in pages):
        return TextLayer(None, f"no page is {PageKind.TEXT}", images, pages)
    return TextLayer(text, images=images, pages=pages)


def _page(pdf: pypdfium2.PdfDocument, index: int) -> LayerPage:
    page = pdf[index]
    try:
        # pdfium returns a turned page's lines last to first.
        turned = page.get_rotation()
        if turned:
            # Its images count still: a picture on it alone gets the idle pass.
            images, segments = drawn_objects(page)
            why = f"page {index + 1} is turned {turned} degrees"
            return LayerPage(None, why, None, images, segments)
        reading = read_page(page)
    finally:
        page.close()
    if reading.kind not in TEXT_USABLE:
        why = f"page {index + 1} is {reading.kind}"
        return LayerPage(None, why, reading.kind, reading.images, reading.segments)
    return LayerPage(reading.text, None, reading.kind, reading.images, reading.segments)
