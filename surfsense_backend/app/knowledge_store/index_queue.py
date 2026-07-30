"""The one way a writer asks for its revision to be indexed.

Both store writers (the editor/upload recorder and the end-of-turn agent commit)
call :func:`enqueue_index` after their content is already committed, so a broker
problem is logged and dropped rather than failing a save that succeeded. The
hourly drift sweep is the backstop for anything lost that way.
"""

from __future__ import annotations

import logging

from app.knowledge_store.settings import load_knowledge_store_settings

logger = logging.getLogger(__name__)


def enqueue_index(workspace_id: int | str) -> None:
    """Ask a worker to fold the store's current revision into the index.

    Only the global kill switch is checked here (sync context, cheap): every
    caller already resolved the per-workspace flag before writing, and the
    worker task re-checks it before converging.
    """
    if not load_knowledge_store_settings().enabled:
        return
    try:
        numeric = int(workspace_id)
    except (TypeError, ValueError):
        # Non-numeric ids exist only in tests, which have no worker to serve them.
        return
    try:
        # Imported here: the task module imports the indexer, which imports the
        # store — a module-level import would close that loop.
        from app.tasks.celery_tasks.knowledge_store_index_tasks import (
            index_knowledge_store_revision,
        )

        index_knowledge_store_revision.delay(numeric)
    except Exception:
        logger.warning(
            "Could not enqueue indexing for workspace %s; "
            "the drift sweep will pick it up",
            workspace_id,
            exc_info=True,
        )
