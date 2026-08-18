"""Resolve the configured :class:`StorageBackend` as a process-wide singleton."""

from __future__ import annotations

from functools import lru_cache

from app.file_storage.backends.base import StorageBackend
from app.file_storage.settings import (
    AZURE_BACKEND,
    LOCAL_BACKEND,
    load_storage_settings,
)


@lru_cache(maxsize=2)
def get_storage_backend(backend_name: str | None = None) -> StorageBackend:
    """Build the selected or recorded storage backend as a singleton."""
    settings = load_storage_settings()
    backend_name = backend_name or settings.backend

    if backend_name == AZURE_BACKEND:
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

    if backend_name == LOCAL_BACKEND:
        from app.file_storage.backends.local import LocalFileBackend

        return LocalFileBackend(settings.local_root)

    raise ValueError(f"Unknown file storage backend: {backend_name!r}")
