"""Maps the model-facing ``[n]`` to its source.

Pydantic for reliable serialization in checkpointed, cross-agent state.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .models import CitationEntry, CitationSourceType


def make_key(source_type: CitationSourceType, locator: dict[str, Any]) -> str:
    """Stable, order-insensitive dedup key; ``source_type`` prefix avoids cross-kind collisions."""
    type_value = (
        source_type.value
        if isinstance(source_type, CitationSourceType)
        else str(source_type)
    )
    return f"{type_value}|{json.dumps(locator, sort_keys=True, default=str)}"


class CitationRegistry(BaseModel):
    """Per-conversation ``[n]`` ↔ unit map (find-or-create, monotonic)."""

    by_n: dict[int, CitationEntry] = Field(default_factory=dict)
    by_key: dict[str, int] = Field(default_factory=dict)
    next_n: int = 1

    def register(
        self,
        source_type: CitationSourceType,
        locator: dict[str, Any],
        display: dict[str, Any] | None = None,
    ) -> int:
        """Return the ``[n]`` for this unit, minting a new one only if unseen."""
        key = make_key(source_type, locator)
        existing = self.by_key.get(key)
        if existing is not None:
            return existing

        n = self.next_n
        self.by_n[n] = CitationEntry(
            n=n,
            source_type=source_type,
            locator=dict(locator),
            display=dict(display or {}),
        )
        self.by_key[key] = n
        self.next_n = n + 1
        return n

    def resolve(self, n: int) -> CitationEntry | None:
        """Map ``[n]`` back to its source; unknown → ``None`` so bad citations drop."""
        return self.by_n.get(n)

    def merge(self, other: CitationRegistry) -> CitationRegistry:
        """Union ``self`` with ``other`` (find-or-create), returning a new registry.

        Needed because separate branches (parent + subagents, parallel tool calls)
        each register into a registry forked from the same base. A plain replace
        would drop one branch's mappings; this unions them so ``[n]`` stays globally
        consistent and no source is lost:

        - A source already in ``self`` keeps its existing ``[n]``.
        - A source only in ``other`` keeps its ``[n]`` when that slot is free.
        - A collision (same ``[n]``, different source on each side) re-mints the
          ``other`` entry to a fresh ``[n]`` and advances ``next_n`` past both.

        Pure: neither registry is mutated. Entries are folded in ascending ``[n]``
        order so the result is deterministic.
        """
        merged = self.model_copy(deep=True)
        for n in sorted(other.by_n):
            entry = other.by_n[n]
            key = make_key(entry.source_type, entry.locator)
            if key in merged.by_key:
                continue
            if n in merged.by_n:
                merged.register(entry.source_type, entry.locator, entry.display)
            else:
                merged.by_n[n] = entry.model_copy(deep=True)
                merged.by_key[key] = n
                merged.next_n = max(merged.next_n, n + 1)
        return merged


__all__ = ["CitationRegistry", "make_key"]
