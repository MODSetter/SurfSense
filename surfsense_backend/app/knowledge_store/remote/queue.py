"""The one way a writer asks for the connected folder to be mirrored."""

from __future__ import annotations

import logging

from app.knowledge_store.settings import load_knowledge_store_settings

logger = logging.getLogger(__name__)


def enqueue_sync(workspace_id: int | str) -> None:
    """Ask a worker to mirror the connected folder, if any.

    Fire-and-forget: a broker problem is logged and dropped. The hourly sweep
    is the backstop.
    """
    if not load_knowledge_store_settings().enabled:
        return
    try:
        numeric = int(workspace_id)
    except (TypeError, ValueError):
        return
    try:
        from app.tasks.celery_tasks.knowledge_store.push_task import (
            push_knowledge_store_revision,
        )

        push_knowledge_store_revision.delay(numeric)
    except Exception:
        logger.warning(
            "Could not enqueue sync for workspace %s; the drift sweep will pick it up",
            workspace_id,
            exc_info=True,
        )


def enqueue_push(workspace_id: int | str) -> None:
    enqueue_sync(workspace_id)
