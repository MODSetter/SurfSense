"""CachedParseRepository against real Postgres: the SQL behind eviction & dedup.

These verify the parts that only a real database can: coldest-first ordering by
reuse then recency, TTL cutoff selection, the size accumulator, and the
insert-once guarantee under a duplicate key.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.etl_pipeline.cache.persistence import CachedParseRepository
from app.etl_pipeline.cache.schemas import ParseKey

pytestmark = pytest.mark.integration


def _key(sha: str) -> ParseKey:
    return ParseKey.for_document(
        sha, etl_service="LLAMACLOUD", mode="basic", version=1
    )


async def _insert(repo, *, sha, size=100, storage_key=None):
    key = _key(sha)
    await repo.insert(
        key=key,
        content_type="application/pdf",
        actual_pages=1,
        storage_backend="local",
        storage_key=storage_key or f"etl_cache/{sha}.md",
        size_bytes=size,
    )
    return key


async def test_total_size_bytes_sums_all_rows(db_session):
    repo = CachedParseRepository(db_session)
    await _insert(repo, sha="a" * 64, size=100)
    await _insert(repo, sha="b" * 64, size=250)

    assert await repo.total_size_bytes() == 350


async def test_select_coldest_orders_by_reuse_then_recency(db_session):
    repo = CachedParseRepository(db_session)
    ka = await _insert(repo, sha="a" * 64)
    kb = await _insert(repo, sha="b" * 64)
    kc = await _insert(repo, sha="c" * 64)

    # Warm B once and C twice; A stays untouched and should be coldest.
    await repo.mark_used((await repo.get(kb)).id)
    await repo.mark_used((await repo.get(kc)).id)
    await repo.mark_used((await repo.get(kc)).id)

    coldest = await repo.select_coldest(limit=10)

    ids_by_reuse = [c.id for c in coldest]
    assert ids_by_reuse[:3] == [
        (await repo.get(ka)).id,
        (await repo.get(kb)).id,
        (await repo.get(kc)).id,
    ]


async def test_select_expired_returns_only_rows_older_than_cutoff(db_session):
    repo = CachedParseRepository(db_session)
    await _insert(repo, sha="a" * 64)

    future = datetime.now(UTC) + timedelta(days=1)
    past = datetime.now(UTC) - timedelta(days=1)

    # Row was just used, so it's older than a future cutoff but not a past one.
    assert len(await repo.select_expired(cutoff=future, limit=10)) == 1
    assert await repo.select_expired(cutoff=past, limit=10) == []


async def test_duplicate_key_insert_keeps_the_first_row(db_session):
    repo = CachedParseRepository(db_session)
    key = await _insert(repo, sha="a" * 64, size=100, storage_key="etl_cache/first.md")

    # Same content-addressed key (a concurrent re-parse): must be a no-op.
    await repo.insert(
        key=key,
        content_type="application/pdf",
        actual_pages=1,
        storage_backend="local",
        storage_key="etl_cache/second.md",
        size_bytes=999,
    )

    row = await repo.get(key)
    assert row.storage_key == "etl_cache/first.md"
    assert await repo.total_size_bytes() == 100
