"""Which reader a PDF's pages go to, said in the log for every PDF Docling reads."""

import logging
from collections.abc import Sequence
from pathlib import Path

from modules.documents.models import Document
from worker.ingestion.docling_batches.joined import joined
from worker.ingestion.docling_batches.page_runs import (
    PageRun,
    batches_of,
    described,
    runs_of,
)
from worker.ingestion.docling_batches.reading import read_batches
from worker.ingestion.figures.idle_pass import queue_idle_figures_pass
from worker.ingestion.pdf_reading.docling_pages import pages_for_docling
from worker.ingestion.pdf_reading.ocr_first import OcrReading, ocr_reading
from worker.ingestion.pdf_reading.ocr_kept import forget_reading
from worker.ingestion.pdf_reading.spliced_text import spliced
from worker.ingestion.pdf_reading.whole_reading import whole_markdown
from worker.ingestion.pdf_text_layer import TextLayer, read_text_layer
from worker.ingestion.pdf_text_layer.page_triage import PageKind
from worker.ingestion.pdf_text_layer.reading import PAGE_BREAK
from worker.jobs import JobYieldedError

logger = logging.getLogger(__name__)

# Enough of the reasons to say why; a long flagged run repeats its own.
_REASONS_SHOWN = 3


def pdf_markdown(document: Document, original: Path) -> str:
    """Raises JobYieldedError when a long reading, Docling's or OCR's, gives the
    queue up, and JobCancelledError when a reading is cancelled."""
    layer = read_text_layer(original)
    if layer.text is not None:
        queue_idle_figures_pass(document, original, layer)
        return layer.text
    if (reading := ocr_reading(original, layer, document)) is not None:
        return _ocr_first_markdown(document, original, reading)
    runs = pages_for_docling(layer)
    if runs is None:
        logger.info("Docling reads %s: %s", original.name, layer.refused_because)
        return whole_markdown(document, original, len(layer.pages) or None)
    logger.info(
        "Docling reads %s %s of %s: %s",
        "page" if sum(len(run.pages) for run in runs) == 1 else "pages",
        described(runs),
        original.name,
        _reasons(layer, runs),
    )
    markdown = spliced(layer, _docling_markdown(document, original, runs))
    # Figures come from the figures-only pass, as for a text-read PDF.
    queue_idle_figures_pass(document, original, layer)
    return markdown


def _ocr_first_markdown(document: Document, original: Path, reading: OcrReading) -> str:
    """OCR's pages with Docling's markdown in place of the pages it reads."""
    runs = runs_of(sorted(reading.docling))
    logger.info(
        "%s reads %d of %d pages of %s in %.1f s%s%s",
        reading.reader,
        reading.read,
        len(reading.layer.pages),
        original.name,
        reading.seconds,
        f", {reading.kept} kept from an earlier run" if reading.kept else "",
        f"; Docling reads {described(runs)}: {_shown(list(reading.docling.values()))}"
        if runs
        else "",
    )
    if runs:
        try:
            docling = _docling_markdown(document, original, runs)
        except JobYieldedError:
            raise
        except Exception:
            # As Docling's batches go: a cancel or a failure starts over, and a
            # source left with ocr/ would look like a reading that gave way.
            forget_reading(original)
            raise
        markdown = spliced(reading.layer, docling)
    else:
        markdown = PAGE_BREAK.join(page.text or "" for page in reading.layer.pages)
    forget_reading(original)
    # A scan's figures wait to be asked for: the pass would read every scanned
    # page with Docling in full, 39 CPU-s a page. Born-digital pages beside them
    # are read by layout alone, so a mixed PDF still gets its idle pass.
    if any(page.kind is PageKind.TEXT for page in reading.layer.pages):
        queue_idle_figures_pass(document, original, reading.layer)
    return markdown


def _docling_markdown(
    document: Document, original: Path, runs: Sequence[PageRun]
) -> list[tuple[PageRun, str]]:
    """Each run's markdown; every batch of every run is read in one go, so a
    yield or a cancel lands between any two."""
    batches = [batch for run in runs for batch in batches_of(run)]
    readings = iter(
        zip(batches, read_batches(document, original, batches), strict=True)
    )
    return [
        (run, joined([next(readings) for _ in batches_of(run)]).export_to_markdown())
        for run in runs
    ]


def _reasons(layer: TextLayer, runs: Sequence[PageRun]) -> str:
    reasons = [layer.pages[n - 1].refused_because for run in runs for n in run.pages]
    return _shown(reasons)


def _shown(reasons: Sequence[str | None]) -> str:
    shown = "; ".join(reason or "" for reason in reasons[:_REASONS_SHOWN])
    more = len(reasons) - _REASONS_SHOWN
    return f"{shown}; and {more} more" if more > 0 else shown
