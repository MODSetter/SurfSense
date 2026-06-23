"""Diff a document's existing chunk rows against its freshly chunked texts.

Embeddings are a pure function of chunk text, so a row whose content reappears
in the new chunking keeps its embedding (and its HNSW/GIN index entries); only
genuinely new texts are embedded and only vanished rows are deleted. Matching
is a greedy multiset match on content in document order, so duplicate
boilerplate chunks pair up one-to-one and reordered chunks become cheap
position updates instead of delete+reinsert.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExistingChunk:
    id: int
    content: str
    position: int


@dataclass(frozen=True, slots=True)
class ChunkPlan:
    """The minimal set of writes that turns the stored chunks into the new ones.

    ``reused`` holds only kept rows whose position actually changed; rows that
    match in place need no write at all. Kept-row count (for metrics) is
    ``len(existing) - len(to_delete)``.
    """

    reused: list[tuple[int, int]]  # (existing_chunk_id, new_position)
    to_embed: list[tuple[int, str]]  # (new_position, text)
    to_delete: list[int]  # existing chunk ids


def reconcile(existing: list[ExistingChunk], new_texts: list[str]) -> ChunkPlan:
    available: dict[str, deque[ExistingChunk]] = defaultdict(deque)
    for chunk in sorted(existing, key=lambda c: c.position):
        available[chunk.content].append(chunk)

    reused: list[tuple[int, int]] = []
    to_embed: list[tuple[int, str]] = []

    for new_position, text in enumerate(new_texts):
        matches = available.get(text)
        if matches:
            chunk = matches.popleft()
            if chunk.position != new_position:
                reused.append((chunk.id, new_position))
        else:
            to_embed.append((new_position, text))

    to_delete = [chunk.id for queue in available.values() for chunk in queue]
    return ChunkPlan(reused=reused, to_embed=to_embed, to_delete=to_delete)
