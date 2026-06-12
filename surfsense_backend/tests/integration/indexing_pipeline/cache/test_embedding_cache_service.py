"""EmbeddingCacheService end-to-end against real Postgres + real local storage.

Exercises the public cache surface -- ``recall`` / ``remember`` -- with no mocks:
a miss returns nothing, a remembered set comes back as equivalent vectors, and a
dimension mismatch is refused rather than served.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingKey, EmbeddingSet
from app.indexing_pipeline.cache.service import EmbeddingCacheService

pytestmark = pytest.mark.integration


def _key(sha: str = "c" * 64, *, dim: int = 4) -> EmbeddingKey:
    return EmbeddingKey(
        markdown_sha256=sha,
        embedding_model="test-model",
        embedding_dim=dim,
        chunker_kind="hybrid",
        chunker_version=1,
    )


async def test_recall_is_a_miss_for_an_unknown_key(db_session, cache_local_storage):
    service = EmbeddingCacheService(db_session)
    assert await service.recall(_key()) is None


async def test_remembered_set_recalls_as_equivalent_vectors(
    db_session, cache_local_storage, clean_embedding_cache_table
):
    service = EmbeddingCacheService(db_session)
    stored = EmbeddingSet(
        summary_embedding=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        chunks=[
            CachedChunk("first chunk", np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)),
            CachedChunk("second chunk", np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)),
        ],
    )

    await service.remember(_key(), stored)
    recalled = await service.recall(_key())

    assert recalled is not None
    assert np.array_equal(recalled.summary_embedding, stored.summary_embedding)
    assert [c.text for c in recalled.chunks] == ["first chunk", "second chunk"]
    assert np.array_equal(recalled.chunks[0].embedding, stored.chunks[0].embedding)
    assert np.array_equal(recalled.chunks[1].embedding, stored.chunks[1].embedding)


async def test_recall_refuses_a_set_whose_dimension_changed(
    db_session, cache_local_storage, clean_embedding_cache_table
):
    # A model kept its name but changed its output width: never serve the stale blob.
    service = EmbeddingCacheService(db_session)
    stored = EmbeddingSet(
        summary_embedding=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
        chunks=[CachedChunk("c", np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32))],
    )
    await service.remember(_key(dim=4), stored)

    # Same identity (model + chunker + markdown), but the caller now expects dim 8.
    recalled = await service.recall(_key(dim=8))

    assert recalled is None
