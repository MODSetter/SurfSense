import importlib
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Hijack `composio` before any `from app.*` import; the `from composio import
# Composio` in app.services.composio_service binds once at first import.
from tests.e2e.fakes import composio_module as _fake_composio

sys.modules["composio"] = _fake_composio

app_config = importlib.import_module("app.config").config
app_db = importlib.import_module("app.db")
Base = app_db.Base
DocumentType = app_db.DocumentType
SearchSourceConnector = app_db.SearchSourceConnector
SearchSourceConnectorType = app_db.SearchSourceConnectorType
SearchSpace = app_db.SearchSpace
User = app_db.User
ConnectorDocument = importlib.import_module(
    "app.indexing_pipeline.connector_document"
).ConnectorDocument
create_default_roles_and_membership = importlib.import_module(
    "app.routes.search_spaces_routes"
).create_default_roles_and_membership
TEST_DATABASE_URL = importlib.import_module("tests.conftest").TEST_DATABASE_URL

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False,
        # Required for asyncpg + savepoints: disables prepared statement cache
        # to prevent "another operation is in progress" errors during savepoint rollbacks.
        connect_args={"prepared_statement_cache_size": 0},
    )

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # drop_all fails on circular FKs (new_chat_threads ↔ public_chat_snapshots).
    # DROP SCHEMA CASCADE handles this without needing topological sort.
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine) -> AsyncSession:
    # Bind the session to a connection that holds an outer transaction.
    # join_transaction_mode="create_savepoint" makes session.commit() release
    # a SAVEPOINT instead of committing the outer transaction, so the final
    # transaction.rollback() undoes everything — including commits made by the
    # service under test — leaving the DB clean for the next test.
    async with async_engine.connect() as conn:
        transaction = await conn.begin()
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
        await transaction.rollback()


@pytest_asyncio.fixture
async def db_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="test@surfsense.net",
        hashed_password="hashed",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def db_connector(
    db_session: AsyncSession, db_user: User, db_search_space: "SearchSpace"
) -> SearchSourceConnector:
    connector = SearchSourceConnector(
        name="Test Connector",
        connector_type=SearchSourceConnectorType.CLICKUP_CONNECTOR,
        config={},
        search_space_id=db_search_space.id,
        user_id=db_user.id,
    )
    db_session.add(connector)
    await db_session.flush()
    return connector


@pytest_asyncio.fixture
async def db_search_space(db_session: AsyncSession, db_user: User) -> SearchSpace:
    space = SearchSpace(
        name="Test Space",
        user_id=db_user.id,
    )
    db_session.add(space)
    await db_session.flush()
    # Mirror POST /searchspaces so routes guarded by check_permission find a membership.
    await create_default_roles_and_membership(db_session, space.id, db_user.id)
    await db_session.flush()
    return space


@pytest.fixture
def patched_summarize(monkeypatch) -> AsyncMock:
    mock = AsyncMock(return_value="Mocked summary.")
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        mock,
    )
    return mock


@pytest.fixture
def patched_summarize_raises(monkeypatch) -> AsyncMock:
    mock = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        mock,
    )
    return mock


@pytest.fixture
def patched_embed_texts(monkeypatch) -> MagicMock:
    mock = MagicMock(side_effect=lambda texts: [[0.1] * _EMBEDDING_DIM for _ in texts])
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.embed_texts",
        mock,
    )
    return mock


@pytest.fixture
def patched_chunk_text(monkeypatch) -> MagicMock:
    mock = MagicMock(return_value=["Test chunk content."])
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text",
        mock,
    )
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text_hybrid",
        mock,
    )
    return mock


@pytest.fixture
def make_connector_document(db_connector, db_user):
    """Integration-scoped override: uses real DB connector and user IDs."""

    def _make(**overrides):
        defaults = {
            "title": "Test Document",
            "source_markdown": "## Heading\n\nSome content.",
            "unique_id": "test-id-001",
            "document_type": DocumentType.CLICKUP_CONNECTOR,
            "search_space_id": db_connector.search_space_id,
            "connector_id": db_connector.id,
            "created_by_id": str(db_user.id),
        }
        defaults.update(overrides)
        return ConnectorDocument(**defaults)

    return _make
