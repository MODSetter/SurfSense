"""Local filesystem backend for development (no cloud credentials required)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from app.file_storage.backends.base import StorageBackend

_CHUNK_SIZE = 1024 * 1024


class LocalFileBackend(StorageBackend):
    """Stores objects as files under a single root directory."""

    backend_name = "local"

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()

    def _path_for(self, key: str) -> Path:
        # Resolve and confirm the key stays inside the root to block traversal.
        target = (self._root / key).resolve()
        if self._root not in target.parents and target != self._root:
            raise ValueError("Resolved storage key escapes the storage root")
        return target

    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        path = self._path_for(key)

        def _write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        await asyncio.to_thread(_write)

    async def open_stream(self, key: str) -> AsyncIterator[bytes]:
        path = self._path_for(key)
        handle = await asyncio.to_thread(path.open, "rb")
        try:
            while True:
                chunk = await asyncio.to_thread(handle.read, _CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)

    async def delete(self, key: str) -> None:
        path = self._path_for(key)

        def _unlink() -> None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass

        await asyncio.to_thread(_unlink)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path_for(key).exists)
