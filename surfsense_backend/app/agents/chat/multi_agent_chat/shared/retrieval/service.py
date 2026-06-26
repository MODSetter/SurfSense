"""Search the knowledge base and render it as model-facing ``<retrieved_context>``.

The retrieval spine end to end: hybrid search → rerank → adapt → render, with
each shown passage registered for ``[n]`` citation along the way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.citations import CitationRegistry
from app.agents.chat.multi_agent_chat.shared.document_render import (
    render_search_context,
)

from .adapter import to_renderable_document
from .hybrid_search import search_chunks
from .models import DocumentHit, SearchScope
from .reranking import rerank_hits

if TYPE_CHECKING:
    from app.services.reranker_service import RerankerService

_DEFAULT_TOP_K = 10


async def search_knowledge_base_context(
    db_session: AsyncSession,
    *,
    workspace_id: int,
    query: str,
    registry: CitationRegistry,
    scope: SearchScope | None = None,
    reranker: RerankerService | None = None,
    top_k: int = _DEFAULT_TOP_K,
) -> str | None:
    """Retrieve KB evidence for ``query`` and render it, registering each ``[n]``.

    Returns ``None`` when nothing matched, so the caller can skip the block.
    """
    hits = await search_chunks(
        db_session,
        workspace_id=workspace_id,
        query=query,
        scope=scope or SearchScope(),
        top_k=top_k,
    )
    return build_context(query, hits, registry, reranker=reranker)


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


__all__ = ["build_context", "search_knowledge_base_context"]
