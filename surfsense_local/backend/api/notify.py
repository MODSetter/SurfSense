from modules.documents.models import Document
from modules.events.broker import EventBroker
from modules.events.schemas import EventKind, InternalEvent


def notify_document_updates(broker: EventBroker, document: Document) -> None:
    """Tell open windows a document's row changed, once the change is committed."""
    _notify(broker, document.workspace_id, document.id, document.status.value)


def notify_document_deleted(
    broker: EventBroker, workspace_id: int, document_id: int
) -> None:
    """Tell open windows a document is gone. Takes ids: the row no longer exists."""
    _notify(broker, workspace_id, document_id, "deleted")


def _notify(
    broker: EventBroker, workspace_id: int, document_id: int, status: str
) -> None:
    """Publish a change the API made itself; the worker's come by `worker/notify.py`."""
    broker.publish(
        InternalEvent(
            workspace_id=workspace_id,
            kind=EventKind.DOCUMENTS,
            ids=[document_id],
            status=status,
        )
    )


def notify_changed(
    broker: EventBroker,
    workspace_id: int,
    kind: EventKind,
    ids: list[int],
    status: str,
) -> None:
    """Tell open windows these rows changed, in one event; nothing for no rows."""
    if ids:
        broker.publish(
            InternalEvent(workspace_id=workspace_id, kind=kind, ids=ids, status=status)
        )
