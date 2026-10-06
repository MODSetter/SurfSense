"""The source a figure belongs to, found only inside the asking workspace."""

from pathlib import Path

from sqlalchemy.orm import Session

from modules.documents.models import Document
from modules.documents.source_figures.layout import figures_dir
from shared.config import get_storage_settings


def source_in_workspace(
    session: Session, workspace_id: int, document_id: int
) -> Document:
    document = session.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise LookupError(f"source {document_id} is not in this workspace")
    return document


def kept_figures_dir(document: Document) -> Path:
    storage = get_storage_settings()
    return figures_dir(storage.document_dir(document.workspace_id, document.id))
