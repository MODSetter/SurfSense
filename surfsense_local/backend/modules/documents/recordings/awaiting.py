"""Recordings that failed for want of a speech model, queued again once one is
chosen, so nothing has to be uploaded twice."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.notify import notify_changed
from modules.documents.models import Document, DocumentStatus
from modules.documents.recordings.metadata import AWAITING, KEY
from modules.documents.tasks import PRIORITY_BULK, ingest_document
from modules.events.broker import EventBroker
from modules.events.schemas import EventKind

__all__ = ["RequeuedRecording", "mark_awaiting_pending", "queue_requeued"]


@dataclass(frozen=True)
class RequeuedRecording:
    workspace_id: int
    document_id: int


def mark_awaiting_pending(session: Session) -> list[RequeuedRecording]:
    """Every waiting recording back to pending, its flag gone. Commit before
    `queue_requeued`: the worker is another process."""
    awaiting = session.scalars(
        select(Document).where(
            Document.status == DocumentStatus.FAILED,
            Document.document_metadata[KEY][AWAITING].as_boolean().is_(True),
        )
    ).all()
    for document in awaiting:
        document.status = DocumentStatus.PENDING
        document.error_message = None
        # Reassigned, not mutated: a JSON column tracks assignment only.
        document.document_metadata = {
            name: value
            for name, value in (document.document_metadata or {}).items()
            if name != KEY
        }
    session.flush()
    return [RequeuedRecording(d.workspace_id, d.id) for d in awaiting]


def queue_requeued(
    requeued: list[RequeuedRecording], broker: EventBroker | None
) -> None:
    """Behind interactive work, as a bulk copy is; each workspace told at once."""
    by_workspace: dict[int, list[int]] = defaultdict(list)
    for recording in requeued:
        ingest_document(recording.document_id, priority=PRIORITY_BULK)
        by_workspace[recording.workspace_id].append(recording.document_id)
    if broker is None:
        return
    for workspace_id, ids in by_workspace.items():
        notify_changed(broker, workspace_id, EventKind.DOCUMENTS, ids, "pending")
