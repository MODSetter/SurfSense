"""Turn retriever ``DocumentHit``s into renderable documents."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
    source_label,
)

from .models import DocumentHit


def to_renderable_document(hit: DocumentHit) -> RenderableDocument:
    """Map one hit to the shape the document-fragment renderer consumes."""
    return RenderableDocument(
        title=hit.title,
        source=source_label(hit.document_type, hit.metadata),
        passages=[
            RenderablePassage(
                content=chunk.content,
                locator={"document_id": hit.document_id, "chunk_id": chunk.chunk_id},
            )
            for chunk in hit.chunks
        ],
    )


__all__ = ["to_renderable_document"]
