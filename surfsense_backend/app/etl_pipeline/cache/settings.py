"""Cache configuration resolved from the central ``Config``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EtlCacheSettings:
    enabled: bool
    parser_version: int
    ttl_days: int
    max_total_bytes: int
    eviction_batch: int
    # None for any storage_* field means: reuse the main file_storage backend.
    storage_backend: str | None
    storage_container: str | None
    storage_local_root: str | None


def load_etl_cache_settings() -> EtlCacheSettings:
    from app.config import config

    return EtlCacheSettings(
        enabled=config.ETL_CACHE_ENABLED,
        parser_version=config.ETL_CACHE_PARSER_VERSION,
        ttl_days=config.ETL_CACHE_TTL_DAYS,
        max_total_bytes=config.ETL_CACHE_MAX_TOTAL_MB * 1024 * 1024,
        eviction_batch=config.ETL_CACHE_EVICTION_BATCH,
        storage_backend=config.ETL_CACHE_STORAGE_BACKEND or None,
        storage_container=config.ETL_CACHE_STORAGE_CONTAINER or None,
        storage_local_root=config.ETL_CACHE_STORAGE_LOCAL_PATH or None,
    )
