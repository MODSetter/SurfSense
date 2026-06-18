"""Real-infra fixtures for the parse-cache integration tests.

``cache_local_storage`` points the cache's blob store at a throwaway directory so
tests exercise the real ``LocalFileBackend`` (no cloud, no mocks). ``clean_cache_table``
removes rows written through the facade's own committing session, which the
savepoint-rolled-back ``db_session`` cannot undo.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest.fixture
def cache_local_storage(tmp_path, monkeypatch):
    from app.config import config
    from app.etl_pipeline.cache.storage.backend import resolve_cache_backend

    monkeypatch.setattr(config, "ETL_CACHE_STORAGE_BACKEND", "local")
    monkeypatch.setattr(config, "ETL_CACHE_STORAGE_LOCAL_PATH", str(tmp_path))
    resolve_cache_backend.cache_clear()
    yield tmp_path
    resolve_cache_backend.cache_clear()


@pytest_asyncio.fixture
async def clean_cache_table(async_engine):
    yield
    async with async_engine.begin() as conn:
        await conn.execute(text("DELETE FROM etl_cache_parses"))
