"""Resolve the configured :class:`StorageBackend` as a process-wide singleton."""

from __future__ import annotations

from functools import lru_cache

from app.file_storage.backends.base import StorageBackend
from app.file_storage.settings import (
    AZURE_BACKEND,
    LOCAL_BACKEND,
    load_storage_settings,
)


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """Build the backend selected by ``FILE_STORAGE_BACKEND`` (lazy-imported)."""
    settings = load_storage_settings()

    if settings.backend == AZURE_BACKEND:
        if not settings.azure_connection_string or not settings.azure_container:
            raise ValueError(
                "Azure storage requires AZURE_STORAGE_CONNECTION_STRING and "
                "AZURE_STORAGE_CONTAINER."
            )
        from app.file_storage.backends.azure import AzureBlobBackend

        return AzureBlobBackend(
            connection_string=settings.azure_connection_string,
            container=settings.azure_container,
        )

    if settings.backend == LOCAL_BACKEND:
        from app.file_storage.backends.local import LocalFileBackend

        return LocalFileBackend(settings.local_root)

    raise ValueError(f"Unknown FILE_STORAGE_BACKEND: {settings.backend!r}")
