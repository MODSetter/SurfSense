import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class ModelBusyError(RuntimeError):
    pass


class ModelActivity:
    """Coordinate generation and deletion for one runtime model."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._uses: dict[tuple[str, str], int] = {}
        self._deleting: set[tuple[str, str]] = set()

    async def acquire_use(self, key: tuple[str, str]) -> None:
        async with self._lock:
            if key in self._deleting:
                raise ModelBusyError("model is being deleted")
            self._uses[key] = self._uses.get(key, 0) + 1

    async def release_use(self, key: tuple[str, str]) -> None:
        async with self._lock:
            remaining = self._uses.get(key, 0) - 1
            if remaining > 0:
                self._uses[key] = remaining
            else:
                self._uses.pop(key, None)

    @asynccontextmanager
    async def deleting(self, key: tuple[str, str]) -> AsyncIterator[None]:
        async with self._lock:
            if self._uses.get(key, 0) > 0 or key in self._deleting:
                raise ModelBusyError("model is currently in use")
            self._deleting.add(key)
        try:
            yield
        finally:
            async with self._lock:
                self._deleting.discard(key)


model_activity = ModelActivity()
