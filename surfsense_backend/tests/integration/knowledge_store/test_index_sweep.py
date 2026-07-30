"""The hourly sweep: the only recovery for indexing lost to a broker or worker.

Every other trigger is fire-and-forget, so if the sweep picks the wrong
candidates or routes them to the wrong queue, a workspace can sit stale
indefinitely with nothing to notice. These tests use real git repos and real
rows; the seam is ``.delay``, the outbound boundary where a task leaves for a
broker that is not running here.
"""

from __future__ import annotations

import pytest

import app.tasks.celery_tasks.knowledge_store_index_tasks as index_tasks
from app.config import config as app_config
from app.db import Workspace
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.identities import user_identity

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def celery_session_on_test_connection(db_session, monkeypatch):
    """Point the sweep's own session maker at the test transaction."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(index_tasks, "get_celery_session_maker", lambda: maker)


@pytest.fixture
def enqueued(monkeypatch):
    """Record which task each workspace was handed to, in call order."""
    calls: list[tuple[str, int]] = []

    def spy(name):
        return lambda workspace_id: calls.append((name, workspace_id))

    monkeypatch.setattr(
        index_tasks.index_knowledge_store_revision, "delay", spy("incremental")
    )
    monkeypatch.setattr(index_tasks.reindex_knowledge_store, "delay", spy("rebuild"))
    return calls


async def make_workspace(session, user_id, *, flipped: bool, stamp: str | None = None):
    space = Workspace(
        name="Swept",
        user_id=user_id,
        knowledge_store_enabled=flipped,
        last_indexed_revision=stamp,
    )
    session.add(space)
    await session.flush()
    return space


async def commit(workspace_id) -> str:
    """Give a workspace a store with one revision in it."""
    store = KnowledgeStore.for_workspace(workspace_id)
    async with store.transaction(message="seed", author=user_identity("1")) as tx:
        tx.write("documents/a.xml", b"# A")
    return tx.revision


# ── Candidate selection ─────────────────────────────────────────────────────


async def test_a_flipped_workspace_trailing_its_store_is_enqueued(
    db_session, db_user, knowledge_root, celery_session_on_test_connection, enqueued
):
    space = await make_workspace(db_session, db_user.id, flipped=True, stamp="stale")
    await commit(space.id)

    assert await index_tasks._sweep() == 1
    assert enqueued == [("incremental", space.id)]


async def test_a_workspace_level_with_its_store_is_left_alone(
    db_session, db_user, knowledge_root, celery_session_on_test_connection, enqueued
):
    space = await make_workspace(db_session, db_user.id, flipped=True)
    space.last_indexed_revision = await commit(space.id)
    await db_session.flush()

    assert await index_tasks._sweep() == 0
    assert enqueued == []


async def test_an_unflipped_workspace_is_never_a_candidate(
    db_session, db_user, knowledge_root, celery_session_on_test_connection, enqueued
):
    """It may have a seeded repo, but Postgres is still its write model."""
    space = await make_workspace(db_session, db_user.id, flipped=False, stamp="stale")
    await commit(space.id)

    assert await index_tasks._sweep() == 0
    assert enqueued == []


async def test_a_workspace_with_no_store_yet_is_skipped(
    db_session, db_user, knowledge_root, celery_session_on_test_connection, enqueued
):
    """Flipped before its seed lands: nothing to converge to, so no task."""
    await make_workspace(db_session, db_user.id, flipped=True)

    assert await index_tasks._sweep() == 0
    assert enqueued == []


# ── Routing ─────────────────────────────────────────────────────────────────


async def test_a_never_indexed_workspace_routes_to_the_rebuild_task(
    db_session, db_user, knowledge_root, celery_session_on_test_connection, enqueued
):
    """A NULL stamp means embedding the whole tree.

    That belongs on the connectors queue with the other rebuilds; sending it to
    the per-save task would put a fleet-wide backfill ahead of user-facing saves
    on the fast queue.
    """
    space = await make_workspace(db_session, db_user.id, flipped=True, stamp=None)
    await commit(space.id)

    assert await index_tasks._sweep() == 1
    assert enqueued == [("rebuild", space.id)]


# ── Fan-out ─────────────────────────────────────────────────────────────────


async def test_the_cap_bounds_the_fan_out_not_the_check(
    db_session,
    db_user,
    knowledge_root,
    celery_session_on_test_connection,
    enqueued,
    monkeypatch,
):
    """Two drifted workspaces, room for one: the other waits for the next run."""
    monkeypatch.setattr(index_tasks, "SWEEP_ENQUEUE_CAP", 1)
    for _ in range(2):
        space = await make_workspace(
            db_session, db_user.id, flipped=True, stamp="stale"
        )
        await commit(space.id)

    assert await index_tasks._sweep() == 1
    assert len(enqueued) == 1
