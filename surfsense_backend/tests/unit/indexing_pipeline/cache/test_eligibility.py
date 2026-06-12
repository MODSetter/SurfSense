from app.indexing_pipeline.cache.eligibility import is_index_cacheable


def test_disabled_cache_is_never_cacheable():
    assert not is_index_cacheable(
        cache_enabled=False, embedding_model="m", embedding_dim=384
    )


def test_missing_model_is_not_cacheable():
    assert not is_index_cacheable(
        cache_enabled=True, embedding_model=None, embedding_dim=384
    )


def test_missing_dimension_is_not_cacheable():
    assert not is_index_cacheable(
        cache_enabled=True, embedding_model="m", embedding_dim=None
    )
    assert not is_index_cacheable(
        cache_enabled=True, embedding_model="m", embedding_dim=0
    )


def test_enabled_with_model_and_dim_is_cacheable():
    assert is_index_cacheable(
        cache_enabled=True, embedding_model="m", embedding_dim=384
    )
