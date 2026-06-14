"""The eviction task on real infra: TTL expiry first, then coldest-over-budget.

Seeds entries through the real cache (DB rows + local blobs), runs the actual
``_evict`` coroutine, and checks what survives via ``recall`` -- no mocks. TTL and
budget are driven through config so each phase can be exercised in isolation.
"""

from __future__ import annotations

import pytest

from app.config import config
from app.etl_pipeline.cache.eviction.task import _evict
from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.service import EtlCacheService
from app.etl_pipeline.etl_document import EtlResult
from app.tasks.celery_tasks import get_celery_session_maker

pytestmark = pytest.mark.integration


def _key(sha: str) -> ParseKey:
    return ParseKey.for_document(
        sha, etl_service="LLAMACLOUD", mode="basic", version=1
    )


def _result(markdown: str) -> EtlResult:
    return EtlResult(
        markdown_content=markdown,
        etl_service="LLAMACLOUD",
        actual_pages=1,
        content_type="application/pdf",
    )


async def _remember(key: ParseKey, result: EtlResult) -> None:
    async with get_celery_session_maker()() as session:
        await EtlCacheService(session).remember(key, result)


async def _recall(key: ParseKey) -> EtlResult | None:
    async with get_celery_session_maker()() as session:
        return await EtlCacheService(session).recall(key)


async def test_expired_entries_are_pruned(
    monkeypatch, cache_local_storage, clean_cache_table
):
    monkeypatch.setattr(config, "ETL_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "ETL_CACHE_TTL_DAYS", -1)  # cutoff in the future -> stale
    monkeypatch.setattr(config, "ETL_CACHE_MAX_TOTAL_MB", 10_000)  # size phase no-op

    key = _key("a" * 64)
    await _remember(key, _result("# stale doc\n"))

    await _evict()

    assert await _recall(key) is None


async def test_coldest_entries_are_shed_when_over_budget(
    monkeypatch, cache_local_storage, clean_cache_table
):
    monkeypatch.setattr(config, "ETL_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "ETL_CACHE_TTL_DAYS", 3650)  # nothing TTL-expired
    monkeypatch.setattr(config, "ETL_CACHE_MAX_TOTAL_MB", 1)  # ~1 MiB budget

    cold = _key("a" * 64)
    warm = _key("b" * 64)
    # Two ~0.6 MiB entries together exceed the 1 MiB budget; one must go.
    await _remember(cold, _result("x" * 600_000))
    await _remember(warm, _result("y" * 600_000))

    # A reuse makes `warm` warmer than `cold`, so `cold` is the eviction target.
    assert await _recall(warm) is not None

    await _evict()

    assert await _recall(cold) is None
    assert await _recall(warm) is not None


async def test_nothing_is_evicted_within_ttl_and_budget(
    monkeypatch, cache_local_storage, clean_cache_table
):
    monkeypatch.setattr(config, "ETL_CACHE_ENABLED", True)
    monkeypatch.setattr(config, "ETL_CACHE_TTL_DAYS", 3650)
    monkeypatch.setattr(config, "ETL_CACHE_MAX_TOTAL_MB", 10_000)

    key = _key("a" * 64)
    await _remember(key, _result("# keep me\n"))

    await _evict()

    assert await _recall(key) is not None
