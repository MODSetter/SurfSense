"""Pure value objects for the embedding cache."""

from __future__ import annotations

from .embedding_key import EmbeddingKey
from .embedding_set import CachedChunk, EmbeddingSet

__all__ = [
    "CachedChunk",
    "EmbeddingKey",
    "EmbeddingSet",
]
