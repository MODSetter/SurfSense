"""Real-infra fixtures for the embedding-cache integration tests.

``cache_local_storage`` points the shared cache backend at a throwaway directory
so tests exercise the real ``LocalFileBackend`` (no cloud, no mocks); the
embedding cache reuses the ETL cache backend, hence the ``ETL_CACHE_STORAGE_*``
knobs. ``clean_embedding_cache_table`` removes rows written through the store's
own committing session, which the savepoint-rolled-back ``db_session`` cannot undo.
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
async def clean_embedding_cache_table(async_engine):
    yield
    async with async_engine.begin() as conn:
        await conn.execute(text("DELETE FROM embedding_cache_sets"))
