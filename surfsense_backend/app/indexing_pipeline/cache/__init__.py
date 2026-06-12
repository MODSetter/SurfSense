"""Content-addressed reuse of chunk+embedding output across workspaces."""

from __future__ import annotations

from app.indexing_pipeline.cache.cached_indexing import build_chunk_embeddings
from app.indexing_pipeline.cache.service import IndexCacheService

__all__ = [
    "IndexCacheService",
    "build_chunk_embeddings",
]
