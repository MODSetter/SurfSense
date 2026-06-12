"""Object keys for cached embedding sets, namespaced under a dedicated prefix."""

from __future__ import annotations

from app.indexing_pipeline.cache.schemas import EmbeddingKey

CACHE_PREFIX = "embedding_cache"


def build_embedding_object_key(key: EmbeddingKey) -> str:
    # Content-addressed: identical markdown + recipe always map to the same key.
    return f"{CACHE_PREFIX}/{key.markdown_sha256}/{key.object_suffix}"
