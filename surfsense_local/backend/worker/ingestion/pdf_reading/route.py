"""Which reader a PDF's pages go to, said in the log for every PDF Docling reads."""

import logging
from collections.abc import Sequence
from pathlib import Path

from modules.documents.models import Document
from worker.ingestion.docling_batches.joined import joined
from worker.ingestion.docling_batches.page_runs import PageRun, batches_of, described
from worker.ingestion.docling_batches.reading import read_batches
from worker.ingestion.figures.idle_pass import queue_idle_figures_pass
from worker.ingestion.pdf_reading.docling_pages import pages_for_docling
from worker.ingestion.pdf_reading.spliced_text import spliced
from worker.ingestion.pdf_reading.whole_reading import whole_markdown
from worker.ingestion.pdf_text_layer import TextLayer, read_text_layer

logger = logging.getLogger(__name__)

# Enough of the reasons to say why; a long flagged run repeats its own.
_REASONS_SHOWN = 3


def pdf_markdown(document: Document, original: Path) -> str:
    """Raises JobYieldedError when a long Docling reading gives the queue up."""
    layer = read_text_layer(original)
    if layer.text is not None:
        queue_idle_figures_pass(document, original, layer)
        return layer.text
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
    shown = "; ".join(reason or "" for reason in reasons[:_REASONS_SHOWN])
    more = len(reasons) - _REASONS_SHOWN
    return f"{shown}; and {more} more" if more > 0 else shown
