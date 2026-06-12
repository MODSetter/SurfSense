"""Background pruning of the index cache by age and size budget."""

from __future__ import annotations

from .task import evict_index_cache_task

__all__ = [
    "evict_index_cache_task",
]
