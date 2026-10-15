from sqlalchemy.orm import Session

from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.original_file import original_path
from modules.documents.source_figures.figure import SourceFigure, from_index_entry
from modules.documents.source_figures.layout import can_hold_figures, read_index
from modules.documents.source_figures.source import (
    kept_figures_dir,
    source_in_workspace,
)
from modules.documents.tasks import extract_figures
from shared.queue import ingest_queue

_INGEST_WILL_KEEP_THEM = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


class FiguresPending(Exception):  # noqa: N818 -- the name the agent's tools import
    """The source's figures are being extracted; ask again shortly."""


def list_figures(
    session: Session, workspace_id: int, document_id: int
) -> list[SourceFigure]:
    """The figures kept from one source, in the order the source shows them.

    A source ingested before figures were kept gets the figures-only pass queued.
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
        _queue_figures_pass(document)
    elif document.status not in _INGEST_WILL_KEEP_THEM:
        return []
    raise FiguresPending(f"the figures of source {document.id} are being extracted")


def _queue_figures_pass(document: Document) -> None:
    # Once is enough: the pass reads the whole file, and a caller polls.
    wanted = extract_figures.s(document.id)
    waiting = any(
        task.name == wanted.name and task.args == wanted.args
        for task in ingest_queue.pending()
    )
    if not waiting:
        ingest_queue.enqueue(wanted)
