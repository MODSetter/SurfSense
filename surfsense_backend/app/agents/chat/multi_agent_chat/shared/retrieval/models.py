"""Value objects for knowledge-base retrieval: the query scope and raw hits.

``SearchScope`` is the optional filter a search runs under. ``DocumentHit`` /
``ChunkHit`` are the retriever's typed output — matched chunks grouped by their
document — which the adapter turns into renderable ``RetrievedDocument``s.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SearchScope:
    """Filters narrowing a search; ``None``/empty means "whole knowledge base"."""

    document_types: tuple[str, ...] | None = None
    document_ids: tuple[int, ...] | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None


@dataclass(frozen=True)
class ChunkHit:
    """One matched chunk, with the position that orders it within its document."""

    chunk_id: int
    content: str
    position: int
    score: float


@dataclass(frozen=True)
class DocumentHit:
    """A document and the chunks that matched the query, ordered by position."""

    document_id: int
    title: str
    document_type: str | None
    metadata: dict[str, Any]
    score: float
    chunks: list[ChunkHit] = field(default_factory=list)


__all__ = ["ChunkHit", "DocumentHit", "SearchScope"]
