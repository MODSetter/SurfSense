"""The figures-only pass: keep a ready source's figures, leaving its text and chunks."""

import logging
from pathlib import Path
from typing import Any

from modules.documents.source_figures.layout import (
    can_hold_figures,
    figures_dir,
    read_index,
)
from worker.ingestion import parsing
from worker.ingestion.figures import pictures_reading
from worker.ingestion.figures.read_source import ready_source, still_ready
from worker.ingestion.figures.scanned_pages import scanned_pages
from worker.ingestion.figures.store import keep_figures, record_figures_failure
from worker.ingestion.image_page import IMAGE_SUFFIXES

logger = logging.getLogger(__name__)


def run(document_id: int) -> None:
    source = ready_source(document_id)
    if source is None or not can_hold_figures(source.original):
        return
    original = source.original
    if read_index(figures_dir(original.parent)) is not None:
        return  # a copy of this pass queued twice, or ingest got there first

    try:
        converted = reading_for_figures(original)
    except Exception as failure:
        if still_ready(source):
            record_figures_failure(original, failure)
        return
    if still_ready(source):
        keep_figures(original, converted)


def reading_for_figures(original: Path) -> Any:
    """Docling's reading of the original, as little of it as its figures need."""
    suffix = original.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return None  # an image is its own figure
    if suffix == ".pdf":
        try:
            scanned = scanned_pages(original)
            if scanned is not None and not all(scanned):
                return pictures_reading.read_for_pictures(original, scanned)
        except Exception:
            # A failure is recorded for good, so it must be the full reading's.
            logger.warning("read %s in full for its figures", original, exc_info=True)
    # Docling reads Word and PowerPoint without models; a scan's captions need OCR.
    return parsing.convert(original)
