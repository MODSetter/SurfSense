"""Reorder retrieved documents with the configured reranker (no-op if disabled).

Ranking is by concatenated matched-chunk content; ``DocumentHit`` order is
rewritten to follow the reranker's result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .models import DocumentHit

if TYPE_CHECKING:
    from app.services.reranker_service import RerankerService


def rerank_hits(
    query: str,
    hits: list[DocumentHit],
    reranker: RerankerService | None,
) -> list[DocumentHit]:
    """Return ``hits`` reordered by the reranker; unchanged when none is set."""
    if reranker is None or len(hits) < 2:
        return hits

    hit_by_id = {hit.document_id: hit for hit in hits}
    ranked = reranker.rerank_documents(query, [_as_document(hit) for hit in hits])
    reordered = [
        hit_by_id[doc["document_id"]]
        for doc in ranked
        if doc.get("document_id") in hit_by_id
    ]
    # Fall back to the original order if the reranker dropped or garbled ids.
    return reordered if len(reordered) == len(hits) else hits


def _as_document(hit: DocumentHit) -> dict[str, Any]:
    """The minimal dict shape ``RerankerService.rerank_documents`` scores on."""
    return {
        "document_id": hit.document_id,
        "content": "\n\n".join(chunk.content for chunk in hit.chunks),
        "score": hit.score,
        "document": {
            "id": hit.document_id,
            "title": hit.title,
            "document_type": hit.document_type,
        },
    }


__all__ = ["rerank_hits"]
