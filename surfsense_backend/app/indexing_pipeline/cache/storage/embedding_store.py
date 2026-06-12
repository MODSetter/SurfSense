"""Read and write cached embedding blobs through the shared cache backend.

The blob backend is shared with the ETL parse cache (same bucket / root), so
markdown and its embeddings live side by side; only the object prefix differs.
"""

from __future__ import annotations

from app.etl_pipeline.cache.storage.backend import resolve_cache_backend
from app.indexing_pipeline.cache.schemas import EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.serialization import deserialize, serialize
from app.indexing_pipeline.cache.storage.object_keys import build_embedding_object_key

_EMBEDDING_CONTENT_TYPE = "application/octet-stream"


class EmbeddingCacheStore:
    def __init__(self) -> None:
        self._backend = resolve_cache_backend()

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    async def save(self, key: EmbeddingKey, embedding_set: EmbeddingSet) -> tuple[str, int]:
        """Persist the embedding set and return its storage key and byte size."""
        blob = serialize(embedding_set)
        storage_key = build_embedding_object_key(key)
        await self._backend.put(
            storage_key, blob, content_type=_EMBEDDING_CONTENT_TYPE
        )
        return storage_key, len(blob)

    async def load(self, storage_key: str) -> EmbeddingSet:
        chunks = [chunk async for chunk in self._backend.open_stream(storage_key)]
        return deserialize(b"".join(chunks))

    async def delete(self, storage_key: str) -> None:
        await self._backend.delete(storage_key)
