"""Read and write cached markdown blobs through the resolved backend."""

from __future__ import annotations

from app.etl_pipeline.cache.schemas import ParseKey
from app.etl_pipeline.cache.storage.backend import resolve_cache_backend
from app.etl_pipeline.cache.storage.object_keys import build_parse_object_key

_MARKDOWN_CONTENT_TYPE = "text/markdown; charset=utf-8"


class MarkdownCacheStore:
    def __init__(self) -> None:
        self._backend = resolve_cache_backend()

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    async def save(self, key: ParseKey, markdown: str) -> str:
        """Persist the markdown and return its storage key for the index row."""
        storage_key = build_parse_object_key(key)
        await self._backend.put(
            storage_key,
            markdown.encode("utf-8"),
            content_type=_MARKDOWN_CONTENT_TYPE,
        )
        return storage_key

    async def load(self, storage_key: str) -> str:
        chunks = [chunk async for chunk in self._backend.open_stream(storage_key)]
        return b"".join(chunks).decode("utf-8")

    async def delete(self, storage_key: str) -> None:
        await self._backend.delete(storage_key)
