"""
Routes for Surfsense documentation.

These endpoints support the citation system for Surfsense docs,
allowing the frontend to fetch document details when a user clicks
on a [citation:doc-XXX] link.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import (
    SurfsenseDocsChunk,
    SurfsenseDocsDocument,
    User,
    get_async_session,
)
from app.schemas.surfsense_docs import (
    SurfsenseDocsChunkRead,
    SurfsenseDocsDocumentWithChunksRead,
)
from app.users import current_active_user

router = APIRouter()


@router.get(
    "/surfsense-docs/by-chunk/{chunk_id}",
    response_model=SurfsenseDocsDocumentWithChunksRead,
)
async def get_surfsense_doc_by_chunk_id(
    chunk_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Retrieves a Surfsense documentation document based on a chunk ID.

    This endpoint is used by the frontend to resolve [citation:doc-XXX] links.
    """
    try:
        # Get the chunk
        chunk_result = await session.execute(
            select(SurfsenseDocsChunk).filter(SurfsenseDocsChunk.id == chunk_id)
        )
        chunk = chunk_result.scalars().first()

        if not chunk:
            raise HTTPException(
                status_code=404,
                detail=f"Surfsense docs chunk with id {chunk_id} not found",
            )

        # Get the associated document with all its chunks
        document_result = await session.execute(
            select(SurfsenseDocsDocument)
            .options(selectinload(SurfsenseDocsDocument.chunks))
            .filter(SurfsenseDocsDocument.id == chunk.document_id)
        )
        document = document_result.scalars().first()

        if not document:
            raise HTTPException(
                status_code=404,
                detail="Surfsense docs document not found",
            )

        # Sort chunks by ID
        sorted_chunks = sorted(document.chunks, key=lambda x: x.id)

        return SurfsenseDocsDocumentWithChunksRead(
            id=document.id,
            title=document.title,
            source=document.source,
            content=document.content,
            chunks=[
                SurfsenseDocsChunkRead(id=c.id, content=c.content)
                for c in sorted_chunks
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve Surfsense documentation: {e!s}",
        ) from e
