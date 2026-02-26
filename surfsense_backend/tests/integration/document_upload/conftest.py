"""Integration conftest — runs the FastAPI app in-process via ASGITransport.

Prerequisites: PostgreSQL + pgvector only.

External system boundaries are mocked:
  - LLM summarization, text embedding, text chunking (external APIs)
  - Redis heartbeat (external infrastructure)
  - Task dispatch is swapped via DI (InlineTaskDispatcher)
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.app import app
from app.config import config as app_config
from app.db import Base
from app.services.task_dispatcher import get_task_dispatcher
from tests.integration.conftest import TEST_DATABASE_URL
from tests.utils.helpers import (
    TEST_EMAIL,
    auth_headers,
    delete_document,
    get_auth_token,
    get_search_space_id,
)

_EMBEDDING_DIM = app_config.embedding_model_instance.dimension
_ASYNCPG_URL = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Inline task dispatcher (replaces Celery via DI — not a mock)
# ---------------------------------------------------------------------------


class InlineTaskDispatcher:
    """Processes files synchronously in the calling coroutine.

    Swapped in via FastAPI dependency_overrides so the upload endpoint
    processes documents inline instead of dispatching to Celery.

    Exceptions are caught to match Celery's fire-and-forget semantics —
    the processing function already marks documents as failed internally.
    """

    async def dispatch_file_processing(
        self,
        *,
        document_id: int,
        temp_path: str,
        filename: str,
        search_space_id: int,
        user_id: str,
    ) -> None:
        from app.tasks.celery_tasks.document_tasks import (
            _process_file_with_document,
        )

        with contextlib.suppress(Exception):
            await _process_file_with_document(
                document_id, temp_path, filename, search_space_id, user_id
            )


app.dependency_overrides[get_task_dispatcher] = lambda: InlineTaskDispatcher()


# ---------------------------------------------------------------------------
# Database setup (ASGITransport skips the app lifespan)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def _ensure_tables():
    """Create DB tables and extensions once per session."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Auth & search space (session-scoped, via the in-process app)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def auth_token(_ensure_tables) -> str:
    """Authenticate once per session, registering the user if needed."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=30.0
    ) as c:
        return await get_auth_token(c)


@pytest.fixture(scope="session")
async def search_space_id(auth_token: str) -> int:
    """Discover the first search space belonging to the test user."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=30.0
    ) as c:
        return await get_search_space_id(c, auth_token)


@pytest.fixture(scope="session")
def headers(auth_token: str) -> dict[str, str]:
    return auth_headers(auth_token)


# ---------------------------------------------------------------------------
# Per-test HTTP client & cleanup
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient]:
    """Per-test async HTTP client using ASGITransport (no running server)."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", timeout=180.0
    ) as c:
        yield c


@pytest.fixture
def cleanup_doc_ids() -> list[int]:
    """Accumulator for document IDs that should be deleted after the test."""
    return []


@pytest.fixture(scope="session", autouse=True)
async def _purge_test_search_space(search_space_id: int):
    """Delete stale documents from previous runs before the session starts."""
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        result = await conn.execute(
            "DELETE FROM documents WHERE search_space_id = $1",
            search_space_id,
        )
        deleted = int(result.split()[-1])
        if deleted:
            print(
                f"\n[purge] Deleted {deleted} stale document(s) "
                f"from search space {search_space_id}"
            )
    finally:
        await conn.close()
    yield


@pytest.fixture(autouse=True)
async def _cleanup_documents(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    cleanup_doc_ids: list[int],
):
    """Delete test documents after every test (API first, DB fallback)."""
    yield

    remaining_ids: list[int] = []
    for doc_id in cleanup_doc_ids:
        try:
            resp = await delete_document(client, headers, doc_id)
            if resp.status_code == 409:
                remaining_ids.append(doc_id)
        except Exception:
            remaining_ids.append(doc_id)

    if remaining_ids:
        conn = await asyncpg.connect(_ASYNCPG_URL)
        try:
            await conn.execute(
                "DELETE FROM documents WHERE id = ANY($1::int[])",
                remaining_ids,
            )
        finally:
            await conn.close()


# ---------------------------------------------------------------------------
# Page-limit helpers (direct DB for setup, API for verification)
# ---------------------------------------------------------------------------


async def _get_user_page_usage(email: str) -> tuple[int, int]:
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        row = await conn.fetchrow(
            'SELECT pages_used, pages_limit FROM "user" WHERE email = $1',
            email,
        )
        assert row is not None, f"User {email!r} not found in database"
        return row["pages_used"], row["pages_limit"]
    finally:
        await conn.close()


async def _set_user_page_limits(
    email: str, *, pages_used: int, pages_limit: int
) -> None:
    conn = await asyncpg.connect(_ASYNCPG_URL)
    try:
        await conn.execute(
            'UPDATE "user" SET pages_used = $1, pages_limit = $2 WHERE email = $3',
            pages_used,
            pages_limit,
            email,
        )
    finally:
        await conn.close()


@pytest.fixture
async def page_limits():
    """Manipulate the test user's page limits (direct DB for setup only).

    Automatically restores original values after each test.
    """

    class _PageLimits:
        async def set(self, *, pages_used: int, pages_limit: int) -> None:
            await _set_user_page_limits(
                TEST_EMAIL, pages_used=pages_used, pages_limit=pages_limit
            )

    original = await _get_user_page_usage(TEST_EMAIL)
    yield _PageLimits()
    await _set_user_page_limits(
        TEST_EMAIL, pages_used=original[0], pages_limit=original[1]
    )


# ---------------------------------------------------------------------------
# Mock external system boundaries
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_external_apis(monkeypatch):
    """Mock LLM, embedding, and chunking — these are external API boundaries."""
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.summarize_document",
        AsyncMock(return_value="Mocked summary."),
    )
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.embed_text",
        MagicMock(return_value=[0.1] * _EMBEDDING_DIM),
    )
    monkeypatch.setattr(
        "app.indexing_pipeline.indexing_pipeline_service.chunk_text",
        MagicMock(return_value=["Test chunk content."]),
    )


@pytest.fixture(autouse=True)
def _mock_redis_heartbeat(monkeypatch):
    """Mock Redis heartbeat — Redis is an external infrastructure boundary."""
    monkeypatch.setattr(
        "app.tasks.celery_tasks.document_tasks._start_heartbeat",
        lambda notification_id: None,
    )
    monkeypatch.setattr(
        "app.tasks.celery_tasks.document_tasks._stop_heartbeat",
        lambda notification_id: None,
    )
    monkeypatch.setattr(
        "app.tasks.celery_tasks.document_tasks._run_heartbeat_loop",
        AsyncMock(),
    )
