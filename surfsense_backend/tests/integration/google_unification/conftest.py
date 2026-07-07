"""Shared fixtures for Google unification integration tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import config as app_config
from app.db import (
    Chunk,
    Document,
    DocumentType,
    SearchSourceConnector,
    SearchSourceConnectorType,
    User,
    Workspace,
)

EMBEDDING_DIM = app_config.embedding_model_instance.dimension
DUMMY_EMBEDDING = [0.1] * EMBEDDING_DIM


def make_document(
    *,
    title: str,
    document_type: DocumentType,
    content: str,
    workspace_id: int,
    created_by_id: str,
) -> Document:
    """Build a Document instance with unique hashes and a dummy embedding."""
    uid = uuid.uuid4().hex[:12]
    return Document(
        title=title,
        document_type=document_type,
        content=content,
        content_hash=f"content-{uid}",
        unique_identifier_hash=f"uid-{uid}",
        source_markdown=content,
        workspace_id=workspace_id,
        created_by_id=created_by_id,
        embedding=DUMMY_EMBEDDING,
        updated_at=datetime.now(UTC),
        status={"state": "ready"},
    )


def make_chunk(*, content: str, document_id: int) -> Chunk:
    return Chunk(
        content=content,
        document_id=document_id,
        embedding=DUMMY_EMBEDDING,
    )


# ---------------------------------------------------------------------------
# Savepoint-based fixture (used by retriever tests that receive db_session)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seed_google_docs(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
):
    """Insert a native Drive doc, a legacy Composio Drive doc, and a FILE doc.

    Returns a dict with keys ``native_doc``, ``legacy_doc``, ``file_doc``,
    plus ``workspace`` and ``user``.
    """
    user_id = str(db_user.id)
    space_id = db_workspace.id

    native_doc = make_document(
        title="Native Drive Document",
        document_type=DocumentType.GOOGLE_DRIVE_FILE,
        content="quarterly report from native google drive connector",
        workspace_id=space_id,
        created_by_id=user_id,
    )
    legacy_doc = make_document(
        title="Legacy Composio Drive Document",
        document_type=DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
        content="quarterly report from composio google drive connector",
        workspace_id=space_id,
        created_by_id=user_id,
    )
    file_doc = make_document(
        title="Uploaded PDF",
        document_type=DocumentType.FILE,
        content="unrelated uploaded file about quarterly reports",
        workspace_id=space_id,
        created_by_id=user_id,
    )

    db_session.add_all([native_doc, legacy_doc, file_doc])
    await db_session.flush()

    native_chunk = make_chunk(
        content="quarterly report from native google drive connector",
        document_id=native_doc.id,
    )
    legacy_chunk = make_chunk(
        content="quarterly report from composio google drive connector",
        document_id=legacy_doc.id,
    )
    file_chunk = make_chunk(
        content="unrelated uploaded file about quarterly reports",
        document_id=file_doc.id,
    )

    db_session.add_all([native_chunk, legacy_chunk, file_chunk])
    await db_session.flush()

    return {
        "native_doc": native_doc,
        "legacy_doc": legacy_doc,
        "file_doc": file_doc,
        "workspace": db_workspace,
        "user": db_user,
    }


# ---------------------------------------------------------------------------
# Committed-data fixture (used by service / browse tests that create their
# own sessions internally and therefore cannot see savepoint-scoped data)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def committed_google_data(async_engine):
    """Insert native, legacy, and FILE docs via a committed transaction.

    Yields ``{"workspace_id": int, "user_id": str}``.
    Cleans up by deleting the workspace (cascades to documents / chunks).
    """
    space_id = None

    async with async_engine.begin() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)

        user = User(
            id=uuid.uuid4(),
            email=f"google-test-{uuid.uuid4().hex[:6]}@surfsense.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        space = Workspace(name=f"Google Test {uuid.uuid4().hex[:6]}", user_id=user.id)
        session.add(space)
        await session.flush()
        space_id = space.id
        user_id = str(user.id)

        native_doc = make_document(
            title="Native Drive Doc",
            document_type=DocumentType.GOOGLE_DRIVE_FILE,
            content="quarterly budget from native google drive",
            workspace_id=space_id,
            created_by_id=user_id,
        )
        legacy_doc = make_document(
            title="Legacy Composio Drive Doc",
            document_type=DocumentType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR,
            content="quarterly budget from composio google drive",
            workspace_id=space_id,
            created_by_id=user_id,
        )
        file_doc = make_document(
            title="Plain File",
            document_type=DocumentType.FILE,
            content="quarterly budget uploaded as file",
            workspace_id=space_id,
            created_by_id=user_id,
        )
        session.add_all([native_doc, legacy_doc, file_doc])
        await session.flush()

        for doc in [native_doc, legacy_doc, file_doc]:
            session.add(
                Chunk(
                    content=doc.content,
                    document_id=doc.id,
                    embedding=DUMMY_EMBEDDING,
                )
            )
        await session.flush()

    yield {"workspace_id": space_id, "user_id": user_id}

    async with async_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM workspaces WHERE id = :sid"), {"sid": space_id}
        )


# ---------------------------------------------------------------------------
# Monkeypatch fixtures for system boundaries
# ---------------------------------------------------------------------------


@pytest.fixture
def patched_session_factory(async_engine, monkeypatch):
    """Replace ``async_session_maker`` in connector_service with one bound to the test engine."""
    test_maker = async_sessionmaker(async_engine, expire_on_commit=False)
    monkeypatch.setattr(
        "app.services.connector_service.async_session_maker", test_maker
    )
    return test_maker


@pytest.fixture
def patched_embed(monkeypatch):
    """Mock the embedding model (system boundary) to return a fixed vector."""
    mock = MagicMock(return_value=DUMMY_EMBEDDING)
    monkeypatch.setattr("app.config.config.embedding_model_instance.embed", mock)
    return mock


# ---------------------------------------------------------------------------
# Indexer test helpers
# ---------------------------------------------------------------------------


def make_session_factory(async_engine):
    """Create a session factory bound to the test engine."""
    return async_sessionmaker(async_engine, expire_on_commit=False)


def mock_task_logger():
    """Return a fully-mocked TaskLoggingService with async methods."""
    from unittest.mock import AsyncMock, MagicMock

    mock = AsyncMock()
    mock.log_task_start = AsyncMock(return_value=MagicMock())
    mock.log_task_progress = AsyncMock()
    mock.log_task_failure = AsyncMock()
    mock.log_task_success = AsyncMock()
    return mock


async def seed_connector(
    async_engine,
    *,
    connector_type: SearchSourceConnectorType,
    config: dict,
    name_prefix: str = "test",
):
    """Seed a connector with committed data. Returns dict and cleanup function.

    Yields ``{"connector_id", "workspace_id", "user_id"}``.
    """
    space_id = None

    async with async_engine.begin() as conn:
        session = AsyncSession(bind=conn, expire_on_commit=False)

        user = User(
            id=uuid.uuid4(),
            email=f"{name_prefix}-{uuid.uuid4().hex[:6]}@surfsense.net",
            hashed_password="hashed",
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        space = Workspace(name=f"{name_prefix} {uuid.uuid4().hex[:6]}", user_id=user.id)
        session.add(space)
        await session.flush()
        space_id = space.id

        connector = SearchSourceConnector(
            name=f"{name_prefix} connector",
            connector_type=connector_type,
            is_indexable=True,
            config=config,
            workspace_id=space_id,
            user_id=user.id,
        )
        session.add(connector)
        await session.flush()
        connector_id = connector.id
        user_id = str(user.id)

    return {
        "connector_id": connector_id,
        "workspace_id": space_id,
        "user_id": user_id,
    }


async def cleanup_space(async_engine, space_id: int):
    """Delete a workspace (cascades to connectors/documents)."""
    async with async_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM workspaces WHERE id = :sid"), {"sid": space_id}
        )
