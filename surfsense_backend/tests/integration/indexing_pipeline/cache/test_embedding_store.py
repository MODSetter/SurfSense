"""EmbeddingCacheStore against a real local filesystem backend (no mocks).

Proves the blob side of the cache: an embedding set written under a
content-addressed key comes back with identical vectors, and a delete actually
removes it.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.storage import EmbeddingCacheStore
from app.indexing_pipeline.cache.storage.object_keys import build_embedding_object_key

pytestmark = pytest.mark.integration


def _key() -> EmbeddingKey:
    return EmbeddingKey(
        markdown_sha256="d" * 64,
        embedding_model="test-model",
        embedding_dim=4,
        chunker_kind="hybrid",
        chunker_version=1,
    )


def _set() -> EmbeddingSet:
    return EmbeddingSet(
        summary_embedding=np.array([0.5, 0.25, 0.125, 0.0625], dtype=np.float32),
        chunks=[
            CachedChunk("café, naïve, 漢字", np.array([1, 2, 3, 4], dtype=np.float32)),
            CachedChunk("second", np.array([5, 6, 7, 8], dtype=np.float32)),
        ],
    )


async def test_save_then_load_round_trips_the_embedding_set(cache_local_storage):
    store = EmbeddingCacheStore()
    embedding_set = _set()

    storage_key, size_bytes = await store.save(_key(), embedding_set)
    loaded = await store.load(storage_key)

    assert storage_key == build_embedding_object_key(_key())
    assert size_bytes > 0
    assert np.array_equal(loaded.summary_embedding, embedding_set.summary_embedding)
    assert [c.text for c in loaded.chunks] == ["café, naïve, 漢字", "second"]
    assert np.array_equal(loaded.chunks[0].embedding, embedding_set.chunks[0].embedding)
    assert np.array_equal(loaded.chunks[1].embedding, embedding_set.chunks[1].embedding)


async def test_delete_removes_the_blob(cache_local_storage):
    store = EmbeddingCacheStore()
    storage_key, _ = await store.save(_key(), _set())

    await store.delete(storage_key)

    # Eviction deleted the blob; a later read must fail rather than serve stale.
    with pytest.raises(FileNotFoundError):
        await store.load(storage_key)
