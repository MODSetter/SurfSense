"""Embedding-cache configuration resolved from the central ``Config``.

The blob backend is intentionally not configured here: it is shared with the ETL
parse cache (see ``ETL_CACHE_STORAGE_*``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingCacheSettings:
    enabled: bool
    chunker_version: int
    ttl_days: int
    max_total_bytes: int
    eviction_batch: int


def load_embedding_cache_settings() -> EmbeddingCacheSettings:
    from app.config import config

    return EmbeddingCacheSettings(
        enabled=config.EMBEDDING_CACHE_ENABLED,
        chunker_version=config.EMBEDDING_CACHE_CHUNKER_VERSION,
        ttl_days=config.EMBEDDING_CACHE_TTL_DAYS,
        max_total_bytes=config.EMBEDDING_CACHE_MAX_TOTAL_MB * 1024 * 1024,
        eviction_batch=config.EMBEDDING_CACHE_EVICTION_BATCH,
    )
