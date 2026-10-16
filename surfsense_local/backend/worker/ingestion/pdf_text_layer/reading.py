"""A PDF's text layer as its text, decided for the whole file: one page Docling
must read sends it the whole file, as before, so no reading is spliced from two."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pypdfium2

from shared import pdfium
from worker.ingestion.pdf_text_layer.filled_fields import holds_filled_fields
from worker.ingestion.pdf_text_layer.page_triage import (
    TEXT_USABLE,
    PageKind,
    read_page,
)
from worker.ingestion.pdf_text_layer.switch import text_layer_on

logger = logging.getLogger(__name__)

# The answer-quality A/B measured pages joined this way (0.70 vs Docling's 0.62).
PAGE_BREAK = "\n\n"


@dataclass(frozen=True)
class TextLayer:
    """The PDF's own text, or None and why Docling must read the file."""

    text: str | None
    refused_because: str | None = None
    # Image objects on its pages: with none, Docling would find few figures.
    images: int = 0


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
        pages = []
        kinds = set()
        images = 0
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                # pdfium returns a turned page's lines last to first.
                turned = page.get_rotation()
                if turned:
                    return TextLayer(
                        None, f"page {index + 1} is turned {turned} degrees"
                    )
                reading = read_page(page)
            finally:
                page.close()
            if reading.kind not in TEXT_USABLE:
                return TextLayer(None, f"page {index + 1} is {reading.kind}")
            pages.append(reading.text)
            kinds.add(reading.kind)
            images += reading.images
    finally:
        pdf.close()
    text = PAGE_BREAK.join(pages)
    if not text.strip():
        return TextLayer(None, "it has no text layer")
    # Covers, titles and stamps alone: whatever else the pages say, only OCR reads.
    if PageKind.TEXT not in kinds:
        return TextLayer(None, f"no page is {PageKind.TEXT}")
    return TextLayer(text, images=images)
