"""Gating rule: may this document be served from / written to the embedding cache?"""

from __future__ import annotations


def is_embedding_cacheable(
    *,
    cache_enabled: bool,
    embedding_model: str | None,
    embedding_dim: int | None,
) -> bool:
    """Cache only when a concrete embedding model and dimension are configured.

    Without a model there is nothing to key against, and without a dimension the
    blob's integrity guard cannot run -- both bypass the cache.
    """
    if not cache_enabled:
        return False
    if not embedding_model:
        return False
    return bool(embedding_dim)
