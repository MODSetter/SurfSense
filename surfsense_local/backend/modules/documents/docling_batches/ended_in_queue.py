"""What a reading that gave the queue up and was then cancelled kept, Docling's
batches and OCR's pages: no run is left to clear them, as a running one does
when it stops."""

import shutil

from modules.documents.docling_batches.layout import docling_dir, ocr_dir
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings

__all__ = ["drop_batches", "drop_when_cancelled_in_queue"]


def drop_when_cancelled_in_queue(document: Document, was: DocumentStatus) -> None:
    if was is DocumentStatus.PENDING and document.document_type is DocumentType.FILE:
        drop_batches(document.workspace_id, document.id)


def drop_batches(workspace_id: int, document_id: int) -> None:
    """Of a file cancelled while it waited; nothing to do for most."""
    folder = get_storage_settings().document_dir(workspace_id, document_id)
    shutil.rmtree(docling_dir(folder), ignore_errors=True)
    shutil.rmtree(ocr_dir(folder), ignore_errors=True)
