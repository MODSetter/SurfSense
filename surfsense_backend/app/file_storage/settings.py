"""Environment-driven configuration for the file-storage module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LOCAL_BACKEND = "local"
AZURE_BACKEND = "azure"

# surfsense_backend/ — two levels up from app/file_storage/settings.py
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOCAL_ROOT = str(_BACKEND_ROOT / ".local_object_store")


@dataclass(frozen=True)
class StorageSettings:
    """Resolved storage configuration for the current process."""

    backend: str
    azure_connection_string: str | None
    azure_container: str | None
    local_root: str


def load_storage_settings() -> StorageSettings:
    """Read storage settings from the environment.

    Defaults to the ``local`` backend so development needs no cloud creds.
    """
    return StorageSettings(
        backend=os.getenv("FILE_STORAGE_BACKEND", LOCAL_BACKEND).strip().lower(),
        azure_connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        azure_container=os.getenv("AZURE_STORAGE_CONTAINER"),
        local_root=os.getenv("FILE_STORAGE_LOCAL_PATH", _DEFAULT_LOCAL_ROOT),
    )
