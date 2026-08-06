"""One writer per document's chunks, once a workspace is git-backed.

The editor's reindex task re-chunks from Postgres ``source_markdown`` and titles
the document from its first heading; the store indexer re-chunks from git and
titles it from the filename. Both running means the title flips on every save and
two writers reconcile the same chunk rows, so the loser's work is silently lost.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.tasks.celery_tasks.document_reindex_tasks as reindex_tasks
from app.config import config as app_config
from app.db import Document, DocumentStatus, DocumentType

pytestmark = pytest.mark.integration


@pytest.fixture
def celery_session_on_test_connection(db_session, monkeypatch):
    """Point the task's own session maker at the test transaction."""
    maker = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(reindex_tasks, "get_celery_session_maker", lambda: maker)


@pytest.fixture
def reindex_spy(monkeypatch):
    calls: list[int] = []

    async def _spy(self, *, document):
        calls.append(document.id)

    monkeypatch.setattr(reindex_tasks.UploadDocumentAdapter, "reindex", _spy)
    return calls


async def make_document(session, workspace_id, user_id) -> Document:
    document = Document(
        title="Editable",
        document_type=DocumentType.NOTE,
        document_metadata={},
        content="# Editable",
        content_hash=f"hash-{uuid.uuid4().hex}",
        unique_identifier_hash=f"unique-{uuid.uuid4().hex}",
        source_markdown="# Editable\n\nBody.",
        workspace_id=workspace_id,
        created_by_id=user_id,
        status=DocumentStatus.ready(),
    )
    session.add(document)
    await session.commit()
    return document


async def test_the_editor_reindex_is_skipped_for_a_git_backed_workspace(
    db_session,
    db_workspace,
    db_user,
    monkeypatch,
    celery_session_on_test_connection,
    reindex_spy,
    workspace_flip,
):
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    workspace_flip(True)
    document = await make_document(db_session, db_workspace.id, db_user.id)

    await reindex_tasks._reindex_document(document.id, str(db_user.id))

    assert reindex_spy == []


async def test_the_editor_reindex_still_runs_for_an_unflipped_workspace(
    db_session,
    db_workspace,
    db_user,
    monkeypatch,
    celery_session_on_test_connection,
    reindex_spy,
    workspace_flip,
):
    """Global flag on, workspace not flipped: Postgres is still the write model."""
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", True)
    workspace_flip(False)
    document = await make_document(db_session, db_workspace.id, db_user.id)

    await reindex_tasks._reindex_document(document.id, str(db_user.id))

    assert reindex_spy == [document.id]


async def test_the_editor_reindex_still_runs_without_the_store(
    db_session,
    db_workspace,
    db_user,
    monkeypatch,
    celery_session_on_test_connection,
    reindex_spy,
):
    """The guard must be conditional, not a quiet disabling of the legacy path."""
    monkeypatch.setattr(app_config, "KNOWLEDGE_STORE_ENABLED", False)
    document = await make_document(db_session, db_workspace.id, db_user.id)

    await reindex_tasks._reindex_document(document.id, str(db_user.id))

    assert reindex_spy == [document.id]
