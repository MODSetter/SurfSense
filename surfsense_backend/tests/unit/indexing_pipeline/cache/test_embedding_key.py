from app.indexing_pipeline.cache.schemas import EmbeddingKey


def _key(**overrides) -> EmbeddingKey:
    base = {
        "markdown_sha256": "a" * 64,
        "embedding_model": "openai://text-embedding-3-small",
        "embedding_dim": 1536,
        "chunker_kind": "hybrid",
        "chunker_version": 1,
    }
    base.update(overrides)
    return EmbeddingKey(**base)


def test_object_suffix_is_stable():
    assert _key().object_suffix == _key().object_suffix


def test_object_suffix_differs_by_model():
    assert _key().object_suffix != _key(embedding_model="local/minilm").object_suffix


def test_object_suffix_differs_by_chunker_kind_and_version():
    assert _key().object_suffix != _key(chunker_kind="code").object_suffix
    assert _key().object_suffix != _key(chunker_version=2).object_suffix


def test_object_suffix_encodes_kind_and_version():
    suffix = _key(chunker_kind="code", chunker_version=3).object_suffix
    assert suffix.endswith(".code.v3.emb")
