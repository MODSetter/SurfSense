"""Recall and remember parser output, coordinating the index and blob store."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.etl_pipeline.cache.persistence import CachedParseRepository
from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.storage import MarkdownCacheStore
from app.etl_pipeline.etl_document import EtlResult

logger = logging.getLogger(__name__)


class EtlCacheService:
    def __init__(self, session: AsyncSession) -> None:
        self._index = CachedParseRepository(session)
        self._store = MarkdownCacheStore()

    async def recall(self, key: ParseKey) -> EtlResult | None:
        """Return the cached result, or None on a miss."""
        row = await self._index.get(key)
        if row is None:
            return None

        try:
            markdown = await self._store.load(row.storage_key)
        except Exception:
            # Index points at a blob that is gone; treat as a miss and re-parse.
            logger.warning("Cache blob missing: %s", row.storage_key, exc_info=True)
            return None

        await self._index.mark_used(row.id)
        return EtlResult(
            markdown_content=markdown,
            etl_service=row.etl_service,
            actual_pages=row.actual_pages,
            content_type=row.content_type,
        )

    async def remember(self, key: ParseKey, result: EtlResult) -> None:
        """Store a freshly parsed result for future reuse."""
        storage_key = await self._store.save(key, result.markdown_content)
        await self._index.insert(
            key=key,
            content_type=result.content_type,
            actual_pages=result.actual_pages,
            storage_backend=self._store.backend_name,
            storage_key=storage_key,
            size_bytes=len(result.markdown_content.encode("utf-8")),
        )
