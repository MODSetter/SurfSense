import numpy as np
import pytest

from app.indexing_pipeline.cache.schemas import CachedChunk, EmbeddingSet
from app.indexing_pipeline.cache.serialization import deserialize, serialize


def _make_set(dim: int, n_chunks: int) -> EmbeddingSet:
    rng = np.random.default_rng(0)
    return EmbeddingSet(
        summary_embedding=rng.random(dim, dtype=np.float64),
        chunks=[
            CachedChunk(text=f"chunk {i}\nwith newline", embedding=rng.random(dim))
            for i in range(n_chunks)
        ],
    )


def test_round_trip_preserves_texts_and_vectors():
    original = _make_set(dim=8, n_chunks=3)

    restored = deserialize(serialize(original))

    assert [c.text for c in restored.chunks] == [c.text for c in original.chunks]
    assert restored.chunk_count == 3
    assert np.allclose(restored.summary_embedding, original.summary_embedding, atol=1e-6)
    for got, want in zip(restored.chunks, original.chunks, strict=True):
        assert np.allclose(got.embedding, want.embedding, atol=1e-6)


def test_round_trip_with_no_chunks():
    original = _make_set(dim=4, n_chunks=0)

    restored = deserialize(serialize(original))

    assert restored.chunk_count == 0
    assert restored.summary_embedding.shape[0] == 4


def test_serialize_rejects_mismatched_dimensions():
    bad = EmbeddingSet(
        summary_embedding=np.zeros(4, dtype=np.float32),
        chunks=[CachedChunk(text="x", embedding=np.zeros(8, dtype=np.float32))],
    )

    with pytest.raises(ValueError):
        serialize(bad)


def test_deserialize_rejects_foreign_blob():
    with pytest.raises(ValueError):
        deserialize(b"not-a-surfsense-blob")
