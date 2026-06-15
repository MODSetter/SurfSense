"""Recall and remember embedding sets, coordinating the index and blob store."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.indexing_pipeline.cache.persistence import CachedEmbeddingSetRepository
from app.indexing_pipeline.cache.schemas import EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.storage import EmbeddingCacheStore

logger = logging.getLogger(__name__)


class EmbeddingCacheService:
    def __init__(self, session: AsyncSession) -> None:
        self._index = CachedEmbeddingSetRepository(session)
        self._store = EmbeddingCacheStore()

    async def recall(self, key: EmbeddingKey) -> EmbeddingSet | None:
        """Return the cached embedding set, or None on a miss."""
        row = await self._index.get(key)
        if row is None:
            return None

        try:
            embedding_set = await self._store.load(row.storage_key)
        except Exception:
            # Index points at a blob that is gone; treat as a miss and re-embed.
            logger.warning("Cache blob missing: %s", row.storage_key, exc_info=True)
            return None

        if int(embedding_set.summary_embedding.shape[0]) != key.embedding_dim:
            # A model swapped its dimension under a reused name; never serve it.
            logger.warning("Cached embedding dimension mismatch: %s", row.storage_key)
            return None

        await self._index.mark_used(row.id)
        return embedding_set

    async def remember(self, key: EmbeddingKey, embedding_set: EmbeddingSet) -> None:
        """Store a freshly embedded set for future reuse."""
        storage_key, size_bytes = await self._store.save(key, embedding_set)
        await self._index.insert(
            key=key,
            storage_backend=self._store.backend_name,
            storage_key=storage_key,
            size_bytes=size_bytes,
            chunk_count=embedding_set.chunk_count,
        )
