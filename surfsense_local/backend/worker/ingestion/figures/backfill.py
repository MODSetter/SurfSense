"""The figures-only pass: keep a ready source's figures, leaving its text and chunks."""

from pathlib import Path

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.original_file import original_path
from modules.documents.source_figures.layout import (
    can_hold_figures,
    figures_dir,
    read_index,
)
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
from worker.ingestion import parsing
from worker.ingestion.figures.store import keep_figures, record_figures_failure
from worker.ingestion.image_page import IMAGE_SUFFIXES


def run(document_id: int) -> None:
    original = _ready_original(document_id)
    if original is None or not can_hold_figures(original):
        return
    if read_index(figures_dir(original.parent)) is not None:
        return  # a copy of this pass queued twice, or ingest got there first

    try:
        # An image is its own figure, so only a document needs reading again.
        converted = (
            None
            if original.suffix.lower() in IMAGE_SUFFIXES
            else parsing.convert(original)
        )
    except Exception as failure:
        record_figures_failure(original, failure)
        return
    keep_figures(original, converted)


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
