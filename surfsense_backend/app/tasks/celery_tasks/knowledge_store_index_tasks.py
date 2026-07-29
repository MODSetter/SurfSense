"""Celery tasks that keep the derived index converged with the store.

One task per store write (enqueued by the writers), one rebuild task, and an
hourly drift sweep that re-drives anything the first two lost.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.db import Workspace
from app.knowledge_store.indexer import index_revision, reindex
from app.knowledge_store.settings import load_knowledge_store_settings
from app.knowledge_store.store import KnowledgeStore
from app.knowledge_store.store_path import stored_workspace_ids
from app.knowledge_store.write_lock import KnowledgeStoreLockError
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

#: Enqueues per sweep. The drift check itself is one HEAD read, but the tasks it
#: fans out each embed, so the cap is what keeps a fleet-wide backfill (the first
#: sweep after enabling the flag) from burying user-facing work.
SWEEP_ENQUEUE_CAP = 100


@celery_app.task(name="index_knowledge_store_revision")
def index_knowledge_store_revision(workspace_id: int) -> int:
    """Fold the workspace store's current revision into the index."""
    if not load_knowledge_store_settings().enabled:
        return 0
    return run_async_celery_task(lambda: _index(workspace_id, full=False))


@celery_app.task(name="reindex_knowledge_store")
def reindex_knowledge_store(workspace_id: int) -> int:
    """Rebuild a workspace's whole index from its current tree."""
    if not load_knowledge_store_settings().enabled:
        return 0
    return run_async_celery_task(lambda: _index(workspace_id, full=True))


@celery_app.task(name="reindex_drifted_workspaces")
def reindex_drifted_workspaces() -> int:
    """Enqueue indexing for workspaces whose stamp trails their store."""
    if not load_knowledge_store_settings().enabled:
        return 0
    return run_async_celery_task(_sweep)


async def _index(workspace_id: int, *, full: bool) -> int:
    """Run one convergence; return how many documents it indexed."""
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        try:
            outcome = await (
                reindex(session, workspace_id)
                if full
                else index_revision(session, workspace_id)
            )
        except KnowledgeStoreLockError:
            # Another indexer holds the workspace and converges to the current
            # revision anyway. If it started before this write landed, the sweep
            # re-drives it; racing it here would just serialize two rebuilds.
            logger.info(
                "Workspace %s is already being indexed; skipping this run",
                workspace_id,
            )
            return 0
        return outcome.indexed


async def _sweep() -> int:
    """Enqueue indexing wherever the stamp disagrees with the store's HEAD."""
    workspace_ids = stored_workspace_ids()
    if not workspace_ids:
        return 0

    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(Workspace.id, Workspace.last_indexed_revision).where(
                Workspace.id.in_(workspace_ids)
            )
        )
        stamps = dict(result.all())

    enqueued = 0
    for workspace_id in workspace_ids:
        if enqueued >= SWEEP_ENQUEUE_CAP:
            logger.info(
                "Drift sweep hit its cap of %d; the rest wait for the next run",
                SWEEP_ENQUEUE_CAP,
            )
            break
        if workspace_id not in stamps:
            # A store whose workspace is gone. Phase 5 owns deleting the repo.
            continue
        head = await KnowledgeStore.for_workspace(workspace_id).get_current_revision()
        if head is None or head == stamps[workspace_id]:
            continue
        index_knowledge_store_revision.delay(workspace_id)
        enqueued += 1

    if enqueued:
        logger.info("Drift sweep enqueued indexing for %d workspaces", enqueued)
    return enqueued
