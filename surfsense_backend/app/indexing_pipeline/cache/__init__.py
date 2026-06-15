"""Content-addressed reuse of chunk+embedding output across workspaces."""

from __future__ import annotations

from app.indexing_pipeline.cache.cached_indexing import build_chunk_embeddings
from app.indexing_pipeline.cache.service import EmbeddingCacheService

__all__ = [
    "EmbeddingCacheService",
    "build_chunk_embeddings",
]
