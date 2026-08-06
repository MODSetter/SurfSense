"""Flipping a workspace also hands the derived index its starting point.

The seed deliberately never reindexes — it copies bytes out of Postgres, so the
existing chunk index already matches what it wrote. A flip that left
``last_indexed_revision`` NULL would throw that away: the drift sweep reads NULL
as never-indexed and enqueues a whole-tree converge that re-embeds everything.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import scripts.migrate_knowledge_store as runner
from app.config import config as app_config
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.migrate import seed_workspace

pytestmark = pytest.mark.integration


@pytest.fixture
def knowledge_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def runner_session_on_test_connection(db_session, monkeypatch):
    """Point the runner's own session maker at the test transaction."""
    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(runner, "async_session_maker", maker)


async def test_flipping_stamps_the_stores_head(
    knowledge_root, db_session, db_workspace, runner_session_on_test_connection
):
    report = await seed_workspace(db_workspace.id, {"documents/a.xml": "# A"})

    await runner._set_flip(db_workspace.id, True)

    await db_session.refresh(db_workspace)
    assert db_workspace.knowledge_store_enabled is True
    assert db_workspace.last_indexed_revision == report.seeded_revision


async def test_a_re_seed_that_recorded_nothing_still_stamps(
    knowledge_root, db_session, db_workspace, runner_session_on_test_connection
):
    """``seeded_revision`` is None on an idempotent re-seed; head is not."""
    await seed_workspace(db_workspace.id, {"documents/a.xml": "# A"})
    re_seed = await seed_workspace(db_workspace.id, {"documents/a.xml": "# A"})

    await runner._set_flip(db_workspace.id, True)

    await db_session.refresh(db_workspace)
    assert re_seed.seeded_revision is None
    head = await KnowledgeStore.for_workspace(db_workspace.id).get_current_revision()
    assert db_workspace.last_indexed_revision == head


async def test_unflipping_clears_the_stamp(
    knowledge_root, db_session, db_workspace, runner_session_on_test_connection
):
    """Postgres owned the chunks while unflipped, so a re-flip must converge fully."""
    await seed_workspace(db_workspace.id, {"documents/a.xml": "# A"})
    await runner._set_flip(db_workspace.id, True)

    await runner._set_flip(db_workspace.id, False)

    await db_session.refresh(db_workspace)
    assert db_workspace.knowledge_store_enabled is False
    assert db_workspace.last_indexed_revision is None


async def test_flipping_without_a_store_leaves_the_stamp_empty(
    knowledge_root, db_session, db_workspace, runner_session_on_test_connection
):
    """--flip only fires on passing parity, but reading a missing head must not raise."""
    await runner._set_flip(db_workspace.id, True)

    await db_session.refresh(db_workspace)
    assert db_workspace.knowledge_store_enabled is True
    assert db_workspace.last_indexed_revision is None
