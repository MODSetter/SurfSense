"""Turn retriever ``DocumentHit``s into renderable documents."""

from __future__ import annotations

from app.agents.chat.multi_agent_chat.shared.citations import CitationSourceType
from app.agents.chat.multi_agent_chat.shared.document_render import (
    RenderableDocument,
    RenderablePassage,
    source_label,
)

from .models import ArtifactHit, KnowledgeHit


def to_renderable_document(hit: KnowledgeHit) -> RenderableDocument:
    """Map one source-qualified hit to the shared document-fragment renderer."""
    if isinstance(hit, ArtifactHit):
        return RenderableDocument(
            title=hit.title,
            source=f"artifact:{hit.path}",
            passages=[
                RenderablePassage(
                    content=chunk.content,
                    locator={
                        "artifact_id": hit.artifact_id,
                        "chunk_id": chunk.chunk_id,
                    },
                    source_type=CitationSourceType.ARTIFACT_CHUNK,
                )
                for chunk in hit.chunks
            ],
        )
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
