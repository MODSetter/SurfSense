"""Render knowledge-base hits as model-facing ``<retrieved_context>``.

The tail of the retrieval spine: rerank → adapt → render, registering each
shown passage for ``[n]`` citation. Hybrid search itself lives in
``hybrid_search``; callers (the ``search_knowledge_base`` tool) pass its hits
straight into :func:`build_context`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.document_render import (
    render_search_context,
)

from .adapter import to_renderable_document
from .models import DocumentHit
from .reranking import rerank_hits

if TYPE_CHECKING:
    from app.services.reranker_service import RerankerService


def build_context(
    query: str,
    hits: list[DocumentHit],
    registry: CitationRegistry,
    *,
    reranker: RerankerService | None = None,
) -> str | None:
    """Rerank → adapt → render. Pure given ``hits``, so it is unit-testable."""
    ranked = rerank_hits(query, hits, reranker)
    documents = [to_renderable_document(hit) for hit in ranked]
    return render_search_context(documents, registry)


__all__ = ["build_context"]
