"""Docling's reading of a whole PDF, its figures kept as ingest reads it."""

from pathlib import Path

import pypdfium2

from modules.documents.models import Document
from shared import pdfium
from worker.ingestion import parsing
from worker.ingestion.docling_batches.joined import joined
from worker.ingestion.docling_batches.page_runs import PageRun, batches_of
from worker.ingestion.docling_batches.reading import read_batches
from worker.ingestion.figures.store import keep_figures


def whole_markdown(document: Document, original: Path, pages: int | None) -> str:
    """Read a batch at a time once it is longer than one; `pages` None: count them."""
    count = pages if pages is not None else _page_count(original)
    batches = batches_of(PageRun(1, count)) if count else []
    if len(batches) <= 1:
        # As before batches, and for a file pdfium cannot read: one conversion.
        converted = parsing.convert(original)
        keep_figures(original, converted)
        return converted.export_to_markdown()
    read = read_batches(document, original, batches)
    reading = joined(list(zip(batches, read, strict=True)))
    keep_figures(original, reading)
    return reading.export_to_markdown()


def _page_count(original: Path) -> int | None:
    try:
        with pdfium.lock:
            pdf = pypdfium2.PdfDocument(original)
            try:
                return len(pdf)
            finally:
                pdf.close()
    except pypdfium2.PdfiumError:
        return None
