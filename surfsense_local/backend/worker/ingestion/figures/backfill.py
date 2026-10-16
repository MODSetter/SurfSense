"""The figures-only pass: keep a ready source's figures, leaving its text and chunks."""

import logging
from pathlib import Path
from typing import Any

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.original_file import original_path
from modules.documents.source_figures.figures_pass import queue_figures_pass
from modules.documents.source_figures.layout import (
    can_hold_figures,
    figures_dir,
    figures_work_dir,
    read_index,
)
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.ingestion import parsing
from worker.ingestion.docling_batches.checkpoint import ReadingCheckpoint
from worker.ingestion.docling_batches.page_runs import BATCH_PAGES
from worker.ingestion.figures import pictures_reading
from worker.ingestion.figures.queue_turn import FiguresPassYieldedError, FiguresTurn
from worker.ingestion.figures.scanned_pages import scanned_pages
from worker.ingestion.figures.store import keep_figures, record_figures_failure
from worker.ingestion.image_page import IMAGE_SUFFIXES

logger = logging.getLogger(__name__)


def run(document_id: int, priority: int) -> None:
    """`priority`: the one this copy was queued with, which a copy queued again
    after giving the queue up keeps."""
    original = _ready_original(document_id)
    if original is None or not can_hold_figures(original):
        return
    if read_index(figures_dir(original.parent)) is not None:
        return  # a copy of this pass queued twice, or ingest got there first

    try:
        converted = reading_for_figures(original, FiguresTurn())
    except FiguresPassYieldedError:
        queue_figures_pass(document_id, priority)
        return
    except Exception as failure:
        record_figures_failure(original, failure)
        return
    keep_figures(original, converted)


def reading_for_figures(original: Path, turn: FiguresTurn | None = None) -> Any:
    """Docling's reading of the original, as little of it as its figures need.
    With `turn`, a PDF's reading may give the queue up between runs, raising
    FiguresPassYieldedError with the runs read kept."""
    suffix = original.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return None  # an image is its own figure
    if suffix == ".pdf":
        try:
            scanned = scanned_pages(original)
            # A long scan too, so that it reads a batch at a time.
            if scanned is not None and (not all(scanned) or len(scanned) > BATCH_PAGES):
                return pictures_reading.read_for_pictures(
                    original,
                    scanned,
                    *_resumable(original, turn),
                )
        except FiguresPassYieldedError:
            raise
        except Exception:
            # A failure is recorded for good, so it must be the full reading's.
            logger.warning("read %s in full for its figures", original, exc_info=True)
    # Docling reads Word and PowerPoint without models; a scan's captions need OCR.
    return parsing.convert(original)


def _resumable(
    original: Path, turn: FiguresTurn | None
) -> tuple[ReadingCheckpoint | None, Any]:
    if turn is None:
        return None, None
    work = figures_work_dir(figures_dir(original.parent))
    return ReadingCheckpoint(work, original), turn.give_way


def _ready_original(document_id: int) -> Path | None:
    # No transaction is held while Docling reads: that takes minutes on a long PDF.
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        with create_session_factory(engine)() as session:
            document = session.get(Document, document_id)
            if (
                document is None
                or document.document_type is not DocumentType.FILE
                or document.status is not DocumentStatus.READY
            ):
                return None
            return original_path(document)
    finally:
        engine.dispose()
