"""Integration conftest — prerequisites: Redis (``REDIS_APP_URL``) only.

Contenders normally wait 10s before giving up; tests shrink that window so
contention cases resolve quickly. The give-up behavior itself is unchanged.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.knowledge_store.locks as write_lock


@pytest.fixture
def workspace_id() -> str:
    """Unique per test so runs never contend with each other or stale keys."""
    return f"it-{uuid.uuid4().hex}"


@pytest.fixture
def short_lock_wait(monkeypatch):
    monkeypatch.setattr(write_lock, "LOCK_WAIT_SECONDS", 0.2)


@pytest.fixture(autouse=True)
def per_doc_sessions(db_session: AsyncSession, monkeypatch):
    """Bind converge's per-document session to the test's connection.

    Converge hands each document its own session for the pipeline's ``index``
    call, which in production is a separate connection so a failing document
    rolls back only itself. The savepoint harness has a single connection, so
    each per-document session is a fresh session on that connection with its own
    savepoint: its rollback unwinds only itself and the converge session's work
    survives — the same isolation the separate connection gives, and it can read
    rows the converge session has committed, which a truly separate connection
    could not see inside the test transaction.
    """

    def maker():
        @contextlib.asynccontextmanager
        async def _ctx() -> AsyncIterator[AsyncSession]:
            conn = await db_session.connection()
            async with AsyncSession(
                bind=conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as doc_session:
                yield doc_session

        return _ctx()

    monkeypatch.setattr(
        "app.tasks.celery_tasks.get_celery_session_maker", lambda: maker
    )
