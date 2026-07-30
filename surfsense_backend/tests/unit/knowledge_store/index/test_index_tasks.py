"""Lock contention: a losing rebuild is redundant, a losing save is not.

A competing rebuild converges the same tree, so the loser skips. The
incremental path must propagate instead — its save may have landed after the
holder read HEAD, and swallowing the error would leave search stale until the
hourly sweep.
"""

from __future__ import annotations

import pytest

import app.tasks.celery_tasks.knowledge_store.index_tasks as index_tasks
from app.knowledge_store.write_lock import KnowledgeStoreLockError

pytestmark = pytest.mark.unit


class _NullSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def contended_workspace(monkeypatch):
    """Both converge functions find the workspace lock held."""

    async def enabled(workspace_id):
        return True

    async def locked(session, workspace_id):
        raise KnowledgeStoreLockError("held")

    monkeypatch.setattr(index_tasks, "knowledge_store_enabled_for", enabled)
    monkeypatch.setattr(index_tasks, "get_celery_session_maker", lambda: _NullSession)
    monkeypatch.setattr(index_tasks, "index_revision", locked)
    monkeypatch.setattr(index_tasks, "reindex", locked)


async def test_a_losing_rebuild_skips(contended_workspace):
    assert await index_tasks._index(1, full=True) == 0


async def test_a_losing_incremental_run_propagates_for_retry(contended_workspace):
    with pytest.raises(KnowledgeStoreLockError):
        await index_tasks._index(1, full=False)


async def test_an_unflipped_workspace_indexes_nothing(monkeypatch):
    async def disabled(workspace_id):
        return False

    monkeypatch.setattr(index_tasks, "knowledge_store_enabled_for", disabled)

    assert await index_tasks._index(1, full=False) == 0
