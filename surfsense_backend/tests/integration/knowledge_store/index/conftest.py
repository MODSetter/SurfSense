"""Shared harness for the converge/index integration tests.

Converge hands each document its own session for the pipeline's ``index`` call,
which in production is a separate connection so a failing document rolls back
only itself. The savepoint harness has a single connection, so each per-document
session is a fresh session on that connection with its own savepoint: its
rollback unwinds only itself and the converge session's work survives — the same
isolation the separate connection gives, reproduced without a second connection.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(autouse=True)
def per_doc_sessions(db_session: AsyncSession, monkeypatch):
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
