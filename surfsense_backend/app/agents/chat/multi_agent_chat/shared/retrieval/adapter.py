"""Turn retriever ``DocumentHit``s into renderable ``RetrievedDocument``s."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.retrieved_context import (
    RetrievedDocument,
    RetrievedPassage,
)

from .models import DocumentHit
from .source_label import source_label


def to_retrieved_document(hit: DocumentHit) -> RetrievedDocument:
    """Map one hit to the shape the ``<retrieved_context>`` renderer consumes."""
    return RetrievedDocument(
        document_id=hit.document_id,
        title=hit.title,
        source_label=source_label(hit.document_type, hit.metadata),
        passages=[
            RetrievedPassage(
                document_id=hit.document_id,
                chunk_id=chunk.chunk_id,
                content=chunk.content,
            )
            for chunk in hit.chunks
        ],
    )


__all__ = ["to_retrieved_document"]
