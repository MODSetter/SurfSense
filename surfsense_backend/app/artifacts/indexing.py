"""Index artifact Markdown into the dedicated artifact tables."""

from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.persistence import Artifact, ArtifactChunk
from app.indexing_pipeline.cache import build_chunk_embeddings
from app.indexing_pipeline.cache.cached_indexing import (
    chunk_markdown_with_lines,
    embed_batch,
)
from app.indexing_pipeline.chunk_reconciler import ExistingChunk, reconcile


async def index_artifact(
    session: AsyncSession,
    *,
    artifact: Artifact,
    markdown: str,
) -> None:
    """Incrementally reconcile an artifact's index in the caller's transaction."""
    artifact.indexing_status = "indexing"
    artifact.indexing_error = None
    await session.flush()

    rows = await session.execute(
        select(
            ArtifactChunk.id,
            ArtifactChunk.content,
            ArtifactChunk.position,
            ArtifactChunk.start_line,
            ArtifactChunk.end_line,
        ).where(ArtifactChunk.artifact_id == artifact.id)
    )
    existing = [
        ExistingChunk(
            id=row.id,
            content=row.content,
            position=row.position,
            start_line=row.start_line,
            end_line=row.end_line,
        )
        for row in rows
    ]

    if not existing:
        summary_embedding, chunks = await build_chunk_embeddings(
            markdown, use_code_chunker=False
        )
        session.add_all(
            ArtifactChunk(
                artifact_id=artifact.id,
                content=chunk.text,
                embedding=chunk.embedding,
                position=position,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
            for position, chunk in enumerate(chunks)
        )
    else:
        chunks = await chunk_markdown_with_lines(markdown, use_code_chunker=False)
        plan = reconcile(existing, chunks)
        embeddings = await embed_batch(
            [markdown, *[chunk.text for chunk in plan.to_embed]]
        )
        summary_embedding, *chunk_embeddings = embeddings

        if plan.reused:
            await session.execute(
                update(ArtifactChunk),
                [
                    {
                        "id": chunk.id,
                        "position": chunk.position,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                    }
                    for chunk in plan.reused
                ],
            )
        if plan.to_delete:
            await session.execute(
                delete(ArtifactChunk).where(ArtifactChunk.id.in_(plan.to_delete))
            )
        session.add_all(
            ArtifactChunk(
                artifact_id=artifact.id,
                content=chunk.text,
                embedding=embedding,
                position=chunk.position,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            )
            for chunk, embedding in zip(plan.to_embed, chunk_embeddings, strict=True)
        )
    artifact.summary_embedding = summary_embedding
    artifact.indexed_generation = artifact.generation
    artifact.indexing_status = "ready"
    artifact.indexing_error = None
