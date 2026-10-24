"""Celery tasks that keep the derived index converged with the store.

One task per store write (enqueued by the writers), one rebuild task, and an
hourly drift sweep that re-drives anything the first two lost.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.celery_app import celery_app
from app.db import Workspace
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.index.converge import index_changes, index_tree
from app.knowledge_store.locks import KnowledgeStoreLockError
from app.knowledge_store.settings import (
    knowledge_store_enabled_for,
    load_knowledge_store_settings,
)
from app.tasks.celery_tasks import get_celery_session_maker, run_async_celery_task

logger = logging.getLogger(__name__)

#: Enqueues per sweep. The drift check itself is one HEAD read, but the tasks it
#: fans out each embed, so the cap is what keeps a fleet-wide backfill (many
#: workspaces flipped at once) from burying user-facing work.
SWEEP_ENQUEUE_CAP = 100

#: A held lock means a converge is in flight; if it read HEAD before this save
#: landed, only a later run picks the save up — so retry rather than leave the
#: save stale until the hourly sweep. A redundant retry no-ops on the stamp.
LOCK_RETRY_DELAY_SECONDS = 30
#: ponytail: 10 x 30s rides out one full rebuild; anything longer-lived falls
#: back to the sweep. Upgrade path is delay scaled to the holder's lock TTL.
LOCK_RETRY_LIMIT = 10


@celery_app.task(
    name="index_knowledge_store_revision", bind=True, max_retries=LOCK_RETRY_LIMIT
)
def index_knowledge_store_revision(self, workspace_id: int) -> int:
    """Fold the workspace store's current revision into the index."""
    if not load_knowledge_store_settings().enabled:
        return 0
    try:
        return run_async_celery_task(lambda: _index(workspace_id, full=False))
    except KnowledgeStoreLockError as exc:
        raise self.retry(countdown=LOCK_RETRY_DELAY_SECONDS, exc=exc) from exc


@celery_app.task(name="reindex_knowledge_store")
def reindex_knowledge_store(workspace_id: int) -> int:
    """Rebuild a workspace's whole index from its current tree."""
    if not load_knowledge_store_settings().enabled:
        return 0
    return run_async_celery_task(lambda: _index(workspace_id, full=True))


@celery_app.task(name="reindex_drifted_workspaces")
def reindex_drifted_workspaces() -> int:
    """Enqueue indexing for flipped workspaces whose stamp trails their store."""
    if not load_knowledge_store_settings().enabled:
        return 0
    return run_async_celery_task(_sweep)


async def _index(workspace_id: int, *, full: bool) -> int:
    """Run one convergence; return how many documents it indexed.

    The per-workspace flag is re-checked here, at the worker: a task can sit
    in the queue across an unflip, and indexing an unflipped workspace would
    put the derived-row writer back in competition with the legacy pipeline.
    """
    if not await knowledge_store_enabled_for(workspace_id):
        logger.info("Workspace %s is not git-backed; not indexing", workspace_id)
        return 0
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        try:
            outcome = await (
                index_tree(session, workspace_id)
                if full
                else index_changes(session, workspace_id)
            )
        except KnowledgeStoreLockError:
            if full:
                # A competing rebuild converges the same tree; racing it would
                # just serialize two identical rebuilds. The sweep re-drives
                # this workspace if anything was missed.
                logger.info(
                    "Workspace %s is already being indexed; skipping this rebuild",
                    workspace_id,
                )
                return 0
            # Incremental: propagate so the task retries after the holder is
            # done — a save landing mid-converge must not wait for the sweep.
            raise
        return outcome.indexed


async def _sweep() -> int:
    """Enqueue indexing wherever the stamp disagrees with the store's HEAD.

    Candidates are **flipped** workspaces only (`workspaces.knowledge_store_enabled`).
    A seeded-but-unflipped workspace has a repo on disk too, but Postgres is
    still its write model — indexing it would fight the legacy pipeline.
    """
    session_maker = get_celery_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(Workspace.id, Workspace.last_indexed_revision).where(
                Workspace.knowledge_store_enabled.is_(True)
            )
        )
        stamps = dict(result.all())

    enqueued = 0
    for workspace_id, stamp in stamps.items():
        if enqueued >= SWEEP_ENQUEUE_CAP:
            logger.info(
                "Drift sweep hit its cap of %d; the rest wait for the next run",
                SWEEP_ENQUEUE_CAP,
            )
            break
        head = await KnowledgeStore.for_workspace(workspace_id).get_current_revision()
        if head is None or head == stamp:
            continue
        if stamp is None:
            # Never indexed: a full converge that embeds the whole tree. Route
            # it with the rebuilds so a backfill can't bury user-facing saves.
            reindex_knowledge_store.delay(workspace_id)
        else:
            index_knowledge_store_revision.delay(workspace_id)
        enqueued += 1

    if enqueued:
        logger.info("Drift sweep enqueued indexing for %d workspaces", enqueued)
    return enqueued
