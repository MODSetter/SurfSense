"""Background pruning of the parse cache by age and size budget."""

from __future__ import annotations

from .task import evict_etl_cache_task

__all__ = [
    "evict_etl_cache_task",
]
