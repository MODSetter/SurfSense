"""Resolve the storage backend for cache blobs: shared main store or a dedicated one."""

from __future__ import annotations

from functools import lru_cache

from app.file_storage.backends.base import StorageBackend


@lru_cache(maxsize=1)
def resolve_cache_backend() -> StorageBackend:
    from app.etl_pipeline.cache.settings import load_etl_cache_settings

    settings = load_etl_cache_settings()

    if not settings.storage_backend:
        from app.file_storage.factory import get_storage_backend

        return get_storage_backend()

    backend = settings.storage_backend.strip().lower()

    if backend == "azure":
        from app.config import config

        if not settings.storage_container:
            raise ValueError("ETL_CACHE_STORAGE_CONTAINER is required for azure cache.")
        if not config.AZURE_STORAGE_CONNECTION_STRING:
            raise ValueError(
                "AZURE_STORAGE_CONNECTION_STRING is required for azure cache."
            )
        from app.file_storage.backends.azure import AzureBlobBackend

        return AzureBlobBackend(
            connection_string=config.AZURE_STORAGE_CONNECTION_STRING,
            container=settings.storage_container,
        )

    if backend == "local":
        if not settings.storage_local_root:
            raise ValueError(
                "ETL_CACHE_STORAGE_LOCAL_PATH is required for local cache."
            )
        from app.file_storage.backends.local import LocalFileBackend

        return LocalFileBackend(settings.storage_local_root)

    raise ValueError(f"Unknown ETL_CACHE_STORAGE_BACKEND: {settings.storage_backend!r}")
