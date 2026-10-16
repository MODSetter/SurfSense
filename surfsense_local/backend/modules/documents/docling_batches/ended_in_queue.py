"""The batches of a reading that gave the queue up and was then cancelled: no run
is left to clear them, as a running one does when it stops."""

import shutil

from modules.documents.docling_batches.layout import docling_dir
from modules.documents.models import Document, DocumentStatus, DocumentType
from shared.config import get_storage_settings

__all__ = ["drop_when_cancelled_in_queue"]


def drop_when_cancelled_in_queue(document: Document, was: DocumentStatus) -> None:
    if was is DocumentStatus.PENDING and document.document_type is DocumentType.FILE:
        folder = get_storage_settings().document_dir(document.workspace_id, document.id)
        shutil.rmtree(docling_dir(folder), ignore_errors=True)
