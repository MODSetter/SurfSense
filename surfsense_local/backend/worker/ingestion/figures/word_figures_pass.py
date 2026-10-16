"""A Word file read without Docling: Docling reads its pictures in the figures pass."""

import logging
from pathlib import Path

from modules.documents.models import Document, DocumentType
from modules.documents.original_file import original_path
from modules.documents.source_figures.figures_pass import queue_figures_pass
from modules.documents.source_figures.layout import figures_dir, read_index
from modules.documents.tasks import PRIORITY_BULK
from worker.ingestion.figures.store import forget_figures, keep_no_figures
from worker.ingestion.figures.word_pictures import WordPictures, pictures_in_word_file

logger = logging.getLogger(__name__)


def leave_figures_to_the_pass(original: Path) -> None:
    """While ingest reads it: an earlier reading's figures go, and a file with no
    picture for Docling to find is indexed with none, so nobody waits on a pass."""
    if pictures_in_word_file(original) is WordPictures.NONE:
        keep_no_figures(original)
    else:
        forget_figures(original)


def queue_figures_pass_once_ready(document: Document) -> None:
    """As its ingest ends, for a Word file that carries images, so a Studio draft
    from it can place them. Behind the ingests already queued: text comes first.

    Never raises: the document is already ready, and figures are extra."""
    try:
        if document.document_type is not DocumentType.FILE:
            return
        original = original_path(document)
        if original is None or original.suffix.lower() != ".docx":
            return
        if read_index(figures_dir(original.parent)) is not None:
            return  # Docling read it and kept them, or there are none
        if pictures_in_word_file(original) is WordPictures.EMBEDDED:
            queue_figures_pass(document.id, PRIORITY_BULK)
    except Exception:
        logger.warning(
            "could not queue the figures of document %s", document.id, exc_info=True
        )
