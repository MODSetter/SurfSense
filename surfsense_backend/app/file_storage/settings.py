"""Configuration for the file-storage module, sourced from the central Config."""

from __future__ import annotations

from dataclasses import dataclass

LOCAL_BACKEND = "local"
AZURE_BACKEND = "azure"


@dataclass(frozen=True)
class StorageSettings:
    """Resolved storage configuration for the current process."""

    backend: str
    azure_connection_string: str | None
    azure_container: str | None
    local_root: str


def load_storage_settings() -> StorageSettings:
    """Resolve storage settings from the central ``Config`` singleton.

    Defaults to the ``local`` backend so development needs no cloud creds.
    """
    from app.config import config

    return StorageSettings(
        backend=config.FILE_STORAGE_BACKEND,
        azure_connection_string=config.AZURE_STORAGE_CONNECTION_STRING,
        azure_container=config.AZURE_STORAGE_CONTAINER,
        local_root=config.FILE_STORAGE_LOCAL_PATH,
    )
