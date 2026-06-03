"""Durable storage for original uploaded files (and future derived artifacts).

Public surface: resolve the configured backend via :func:`get_storage_backend`
and persist/retrieve a document's files via :mod:`app.file_storage.service`.
"""

from __future__ import annotations

from app.file_storage.backends.base import StorageBackend
from app.file_storage.factory import get_storage_backend

__all__ = [
    "StorageBackend",
    "get_storage_backend",
]
