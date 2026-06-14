"""CachedEmbeddingSetRepository against real Postgres: the SQL behind eviction & dedup.

These verify the parts only a real database can: the size accumulator,
coldest-first ordering by reuse then recency, TTL cutoff selection, the
insert-once guarantee under a duplicate key, and the reuse counter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.indexing_pipeline.cache.persistence import CachedEmbeddingSetRepository
from app.indexing_pipeline.cache.schemas import EmbeddingKey

pytestmark = pytest.mark.integration


def _key(sha: str) -> EmbeddingKey:
    return EmbeddingKey(
        markdown_sha256=sha,
        embedding_model="test-model",
        embedding_dim=4,
        chunker_kind="hybrid",
        chunker_version=1,
    )


async def _insert(repo, *, sha, size=100, storage_key=None, chunk_count=1):
    key = _key(sha)
    await repo.insert(
        key=key,
        storage_backend="local",
        storage_key=storage_key or f"embedding_cache/{sha}.emb",
        size_bytes=size,
        chunk_count=chunk_count,
    )
    return key


async def test_total_size_bytes_sums_all_rows(db_session):
    repo = CachedEmbeddingSetRepository(db_session)
    await _insert(repo, sha="a" * 64, size=100)
    await _insert(repo, sha="b" * 64, size=250)

    assert await repo.total_size_bytes() == 350


async def test_select_coldest_orders_by_reuse_then_recency(db_session):
    repo = CachedEmbeddingSetRepository(db_session)
    ka = await _insert(repo, sha="a" * 64)
    kb = await _insert(repo, sha="b" * 64)
    kc = await _insert(repo, sha="c" * 64)

    # Warm B once and C twice; A stays untouched and should be coldest.
    await repo.mark_used((await repo.get(kb)).id)
    await repo.mark_used((await repo.get(kc)).id)
    await repo.mark_used((await repo.get(kc)).id)

    coldest = await repo.select_coldest(limit=10)

    assert [c.id for c in coldest][:3] == [
        (await repo.get(ka)).id,
        (await repo.get(kb)).id,
        (await repo.get(kc)).id,
    ]


async def test_select_expired_returns_only_rows_older_than_cutoff(db_session):
    repo = CachedEmbeddingSetRepository(db_session)
    await _insert(repo, sha="a" * 64)

    future = datetime.now(UTC) + timedelta(days=1)
    past = datetime.now(UTC) - timedelta(days=1)

    # Row was just used, so it predates a future cutoff but not a past one.
    assert len(await repo.select_expired(cutoff=future, limit=10)) == 1
    assert await repo.select_expired(cutoff=past, limit=10) == []


async def test_duplicate_key_insert_keeps_the_first_row(db_session):
    repo = CachedEmbeddingSetRepository(db_session)
    key = await _insert(
        repo, sha="a" * 64, size=100, storage_key="embedding_cache/first.emb"
    )

    # Same content-addressed key (a concurrent re-embed): must be a no-op.
    await repo.insert(
        key=key,
        storage_backend="local",
        storage_key="embedding_cache/second.emb",
        size_bytes=999,
        chunk_count=42,
    )

    row = await repo.get(key)
    assert row.storage_key == "embedding_cache/first.emb"
    assert await repo.total_size_bytes() == 100


async def test_mark_used_increments_reuse_count(db_session):
    repo = CachedEmbeddingSetRepository(db_session)
    key = await _insert(repo, sha="a" * 64)
    assert (await repo.get(key)).times_reused == 0

    await repo.mark_used((await repo.get(key)).id)
    await repo.mark_used((await repo.get(key)).id)

    assert (await repo.get(key)).times_reused == 2
