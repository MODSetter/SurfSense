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

from app.indexing_pipeline.document_chunker import LineChunk


@dataclass(frozen=True, slots=True)
class ExistingChunk:
    id: int
    content: str
    position: int
    #: ``None`` on rows written before line spans existed.
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True, slots=True)
class ReusedChunk:
    """A kept row whose position or line range needs writing back."""

    id: int
    position: int
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class PendingChunk:
    """A new text that has to be embedded and inserted."""

    position: int
    text: str
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class ChunkPlan:
    """The minimal set of writes that turns the stored chunks into the new ones.

    ``reused`` holds only kept rows that actually changed — position or line
    range; rows identical in both need no write at all. Kept-row count (for
    metrics) is ``len(existing) - len(to_delete)``.
    """

    reused: list[ReusedChunk]
    to_embed: list[PendingChunk]
    to_delete: list[int]  # existing chunk ids


def reconcile(existing: list[ExistingChunk], new_chunks: list[LineChunk]) -> ChunkPlan:
    available: dict[str, deque[ExistingChunk]] = defaultdict(deque)
    for chunk in sorted(existing, key=lambda c: c.position):
        available[chunk.content].append(chunk)

    reused: list[ReusedChunk] = []
    to_embed: list[PendingChunk] = []

    for new_position, new_chunk in enumerate(new_chunks):
        matches = available.get(new_chunk.text)
        if matches:
            chunk = matches.popleft()
            # Unchanged text still moves when a paragraph is inserted above it:
            # same embedding, different lines. Both have to be written back.
            if (chunk.position, chunk.start_line, chunk.end_line) != (
                new_position,
                new_chunk.start_line,
                new_chunk.end_line,
            ):
                reused.append(
                    ReusedChunk(
                        id=chunk.id,
                        position=new_position,
                        start_line=new_chunk.start_line,
                        end_line=new_chunk.end_line,
                    )
                )
        else:
            to_embed.append(
                PendingChunk(
                    position=new_position,
                    text=new_chunk.text,
                    start_line=new_chunk.start_line,
                    end_line=new_chunk.end_line,
                )
            )

    to_delete = [chunk.id for queue in available.values() for chunk in queue]
    return ChunkPlan(reused=reused, to_embed=to_embed, to_delete=to_delete)
