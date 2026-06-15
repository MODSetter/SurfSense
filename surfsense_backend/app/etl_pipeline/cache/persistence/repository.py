"""CRUD and eviction selectors for ``etl_cache_parses`` (no business rules)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl_pipeline.cache.schemas import EvictionCandidate, ParseKey

from .models import CachedParse

_EVICTION_COLUMNS = (
    CachedParse.id,
    CachedParse.storage_key,
    CachedParse.size_bytes,
    CachedParse.last_used_at,
    CachedParse.times_reused,
)


def _as_eviction_candidate(row) -> EvictionCandidate:
    return EvictionCandidate(
        id=row.id,
        storage_key=row.storage_key,
        size_bytes=row.size_bytes,
        last_used_at=row.last_used_at,
        times_reused=row.times_reused,
    )


class CachedParseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, key: ParseKey) -> CachedParse | None:
        result = await self._session.execute(
            select(CachedParse).where(
                CachedParse.source_sha256 == key.source_sha256,
                CachedParse.etl_service == key.etl_service,
                CachedParse.mode == key.mode,
                CachedParse.parser_version == key.version,
            )
        )
        return result.scalars().first()

    async def insert(
        self,
        *,
        key: ParseKey,
        content_type: str,
        actual_pages: int,
        storage_backend: str,
        storage_key: str,
        size_bytes: int,
    ) -> None:
        # Concurrent writers parse identical bytes, so a lost race is harmless.
        now = datetime.now(UTC)
        await self._session.execute(
            pg_insert(CachedParse)
            .values(
                source_sha256=key.source_sha256,
                etl_service=key.etl_service,
                mode=key.mode,
                parser_version=key.version,
                content_type=content_type,
                actual_pages=actual_pages,
                storage_backend=storage_backend,
                storage_key=storage_key,
                size_bytes=size_bytes,
                times_reused=0,
                last_used_at=now,
                created_at=now,
            )
            .on_conflict_do_nothing(constraint="uq_etl_cache_parses_key")
        )
        await self._session.commit()

    async def mark_used(self, row_id: int) -> None:
        await self._session.execute(
            update(CachedParse)
            .where(CachedParse.id == row_id)
            .values(
                times_reused=CachedParse.times_reused + 1,
                last_used_at=datetime.now(UTC),
            )
        )
        await self._session.commit()

    async def total_size_bytes(self) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(CachedParse.size_bytes), 0))
        )
        return int(result.scalar() or 0)

    async def select_expired(
        self, *, cutoff: datetime, limit: int
    ) -> list[EvictionCandidate]:
        result = await self._session.execute(
            select(*_EVICTION_COLUMNS)
            .where(CachedParse.last_used_at < cutoff)
            .order_by(CachedParse.last_used_at.asc())
            .limit(limit)
        )
        return [_as_eviction_candidate(row) for row in result]

    async def select_coldest(self, *, limit: int) -> list[EvictionCandidate]:
        result = await self._session.execute(
            select(*_EVICTION_COLUMNS)
            .order_by(CachedParse.times_reused.asc(), CachedParse.last_used_at.asc())
            .limit(limit)
        )
        return [_as_eviction_candidate(row) for row in result]

    async def delete_by_ids(self, ids: list[int]) -> None:
        if not ids:
            return
        await self._session.execute(delete(CachedParse).where(CachedParse.id.in_(ids)))
        await self._session.commit()
