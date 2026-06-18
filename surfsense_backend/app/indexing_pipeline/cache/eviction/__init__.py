"""Background pruning of the embedding cache by age and size budget."""

from __future__ import annotations

from .task import evict_embedding_cache_task

__all__ = [
    "evict_embedding_cache_task",
]
