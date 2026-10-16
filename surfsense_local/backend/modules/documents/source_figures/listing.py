from sqlalchemy.orm import Session

from modules.documents.models import DocumentStatus, DocumentType
from modules.documents.original_file import original_path
from modules.documents.source_figures.figure import SourceFigure, from_index_entry
from modules.documents.source_figures.figures_pass import queue_figures_pass
from modules.documents.source_figures.layout import can_hold_figures, read_index
from modules.documents.source_figures.source import (
    kept_figures_dir,
    source_in_workspace,
)
from modules.documents.tasks import PRIORITY_ASKED

# Still being read: ingest keeps them, or settles a Word file's as it ends.
_INGEST_WILL_KEEP_THEM = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class FiguresPending(Exception):  # noqa: N818 -- the name the agent's tools import
    """The source's figures are being extracted; ask again shortly."""


def list_figures(
    session: Session, workspace_id: int, document_id: int
) -> list[SourceFigure]:
    """The figures kept from one source, in the order the source shows them.

    A ready source ingest left without them gets the figures-only pass queued:
    a PDF read from its text layer, a Word file read without Docling, or one
    ingested before figures were kept.
    """
    document = source_in_workspace(session, workspace_id, document_id)
    if document.document_type is not DocumentType.FILE:
        return []

    entries = read_index(kept_figures_dir(document))
    if entries is not None:
        return [from_index_entry(document.id, entry) for entry in entries]

    original = original_path(document)
    if original is None or not can_hold_figures(original):
        return []
    if document.status is DocumentStatus.READY:
        # Someone is waiting on it: ahead of a folder import, behind a note.
        queue_figures_pass(document.id, PRIORITY_ASKED)
    elif document.status not in _INGEST_WILL_KEEP_THEM:
        return []
    raise FiguresPending(f"the figures of source {document.id} are being extracted")
