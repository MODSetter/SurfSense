"""SQLAlchemy session event hooks — wired once at app startup.

Detects document folder arrivals across every ORM commit and publishes
``document.entered_folder`` events to the bus after the transaction is durable.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import event
from sqlalchemy.orm import Session, attributes

from app.db import Document, DocumentStatus
from app.event_bus.bus import EventBus, bus as default_bus
from app.event_bus.events.document_entered_folder import payload_if_entered_folder

logger = logging.getLogger(__name__)

_PENDING_KEY = "_entered_folder_pending"


def _after_flush(session: Session, flush_context: object) -> None:
    """Collect folder-arrival candidates while attribute history is still available."""
    pending: list[dict] = []

    for obj in list(session.new) + list(session.dirty):
        if not isinstance(obj, Document):
            continue

        history = attributes.get_history(obj, "folder_id")
        if not history.added:
            continue

        new_folder_id = history.added[0]
        previous_folder_id = history.deleted[0] if history.deleted else None

        result = payload_if_entered_folder(
            document_id=obj.id,
            workspace_id=obj.workspace_id,
            new_folder_id=new_folder_id,
            previous_folder_id=previous_folder_id,
            folder_id_changed=True,
            status_state=DocumentStatus.get_state(obj.status) or "",
            document_type=obj.document_type.value if obj.document_type else "",
            title=obj.title or "",
            connector_id=obj.connector_id,
            created_by_id=str(obj.created_by_id) if obj.created_by_id else None,
        )
        if result is not None:
            pending.append(result)

    setattr(session, _PENDING_KEY, pending)


def _after_commit(session: Session) -> None:
    """Publish collected events now that the transaction is durable."""
    pending: list[dict] = getattr(session, _PENDING_KEY, [])
    if not pending:
        return
    setattr(session, _PENDING_KEY, [])

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No running event loop — skipping %d event(s)", len(pending))
        return

    tasks = [
        loop.create_task(
            default_bus.publish(
                item["event_type"],
                item["payload"],
                workspace_id=item["workspace_id"],
            )
        )
        for item in pending
    ]
    for task in tasks:
        task.add_done_callback(
            lambda t: (
                logger.error("event publish failed: %s", t.exception())
                if not t.cancelled() and t.exception()
                else None
            )
        )


def _after_rollback(session: Session) -> None:
    """Discard any pending events — the transaction did not commit."""
    setattr(session, _PENDING_KEY, [])


def register_session_hooks(bus: EventBus = default_bus) -> None:
    """Register document folder-arrival hooks on the SQLAlchemy Session class.

    Call once at application startup (e.g. in ``app.app`` lifespan). Idempotent
    — SQLAlchemy deduplicates identical listener registrations.
    """
    event.listen(Session, "after_flush", _after_flush)
    event.listen(Session, "after_commit", _after_commit)
    event.listen(Session, "after_rollback", _after_rollback)
