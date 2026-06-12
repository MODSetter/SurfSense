"""CRUD and eviction selectors for ``index_cache_embedding_sets`` (no business rules)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl_pipeline.cache.schemas import EvictionCandidate
from app.indexing_pipeline.cache.schemas import EmbeddingKey

from .models import CachedEmbeddingSet

_EVICTION_COLUMNS = (
    CachedEmbeddingSet.id,
    CachedEmbeddingSet.storage_key,
    CachedEmbeddingSet.size_bytes,
    CachedEmbeddingSet.last_used_at,
    CachedEmbeddingSet.times_reused,
)


def _as_eviction_candidate(row) -> EvictionCandidate:
    return EvictionCandidate(
        id=row.id,
        storage_key=row.storage_key,
        size_bytes=row.size_bytes,
        last_used_at=row.last_used_at,
        times_reused=row.times_reused,
    )


class CachedEmbeddingSetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: EmbeddingKey) -> CachedEmbeddingSet | None:
        result = await self._session.execute(
            select(CachedEmbeddingSet).where(
                CachedEmbeddingSet.markdown_sha256 == key.markdown_sha256,
                CachedEmbeddingSet.embedding_model == key.embedding_model,
                CachedEmbeddingSet.chunker_kind == key.chunker_kind,
                CachedEmbeddingSet.chunker_version == key.chunker_version,
            )
        )
        return result.scalars().first()

    async def insert(
        self,
        *,
        key: EmbeddingKey,
        storage_backend: str,
        storage_key: str,
        size_bytes: int,
        chunk_count: int,
    ) -> None:
        # Concurrent writers embed identical markdown, so a lost race is harmless.
        now = datetime.now(UTC)
        await self._session.execute(
            pg_insert(CachedEmbeddingSet)
            .values(
                markdown_sha256=key.markdown_sha256,
                embedding_model=key.embedding_model,
                embedding_dim=key.embedding_dim,
                chunker_kind=key.chunker_kind,
                chunker_version=key.chunker_version,
                storage_backend=storage_backend,
                storage_key=storage_key,
                size_bytes=size_bytes,
                chunk_count=chunk_count,
                times_reused=0,
                last_used_at=now,
                created_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_index_cache_embedding_sets_key")
        )
        await self._session.commit()

    async def mark_used(self, row_id: int) -> None:
        await self._session.execute(
            update(CachedEmbeddingSet)
            .where(CachedEmbeddingSet.id == row_id)
            .values(
                times_reused=CachedEmbeddingSet.times_reused + 1,
                last_used_at=datetime.now(UTC),
            )
        )
        await self._session.commit()

    async def total_size_bytes(self) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(CachedEmbeddingSet.size_bytes), 0))
        )
        return int(result.scalar() or 0)

    async def select_expired(
        self, *, cutoff: datetime, limit: int
    ) -> list[EvictionCandidate]:
        result = await self._session.execute(
            select(*_EVICTION_COLUMNS)
            .where(CachedEmbeddingSet.last_used_at < cutoff)
            .order_by(CachedEmbeddingSet.last_used_at.asc())
            .limit(limit)
        )
        return [_as_eviction_candidate(row) for row in result]

    async def select_coldest(self, *, limit: int) -> list[EvictionCandidate]:
        result = await self._session.execute(
            select(*_EVICTION_COLUMNS)
            .order_by(
                CachedEmbeddingSet.times_reused.asc(),
                CachedEmbeddingSet.last_used_at.asc(),
            )
            .limit(limit)
        )
        return [_as_eviction_candidate(row) for row in result]

    async def delete_by_ids(self, ids: list[int]) -> None:
        if not ids:
            return
        await self._session.execute(
            delete(CachedEmbeddingSet).where(CachedEmbeddingSet.id.in_(ids))
        )
        await self._session.commit()
