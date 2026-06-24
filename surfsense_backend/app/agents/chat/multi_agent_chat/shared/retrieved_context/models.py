"""Data shapes for retrieved knowledge-base evidence.

A passage is one matched chunk (the citable unit); a document groups the
passages that came from the same source. The renderer turns these into the
model-facing ``<retrieved_context>`` block.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievedPassage:
    """One matched chunk: the unit the model cites with ``[n]``."""

    document_id: int
    chunk_id: int
    content: str


@dataclass(frozen=True)
class RetrievedDocument:
    """A source document and the passages retrieved from it, in order.

    ``is_complete`` is ``True`` when every chunk of the document is present in
    this block, so the model knows whether it is seeing the whole source or
    only excerpts.
    """

    document_id: int
    title: str
    source_label: str | None = None
    is_complete: bool = False
    passages: list[RetrievedPassage] = field(default_factory=list)


__all__ = ["RetrievedDocument", "RetrievedPassage"]
