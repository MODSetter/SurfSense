"""The storage backend contract: the minimal object-store surface we depend on."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, AsyncIterator


class StorageBackend(ABC):
    """Maps an opaque object key to durable bytes."""

    #: Identifier stored on each row to record which backend holds the bytes.
    backend_name: str

    @abstractmethod
    async def put(
        self, key: str, data: bytes, *, content_type: str | None = None
    ) -> None:
        """Store ``data`` at ``key``, overwriting any existing object."""

    @abstractmethod
    async def put_stream(
        self,
        key: str,
        chunks: AsyncIterable[bytes],
        *,
        content_type: str | None = None,
    ) -> None:
        """Store an async byte stream without materializing the whole object."""

    @abstractmethod
    def open_stream(self, key: str) -> AsyncIterator[bytes]:
        """Yield the object's bytes in chunks. Raises if the key is absent."""

    @abstractmethod
    def open_range(self, key: str, start: int, end: int) -> AsyncIterator[bytes]:
        """Yield the inclusive byte range ``start`` through ``end``."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object at ``key``; a missing key is not an error."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return whether an object is stored at ``key``."""
