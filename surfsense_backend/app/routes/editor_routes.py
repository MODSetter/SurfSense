"""
Editor routes for BlockNote document editing.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, SearchSpace, User, get_async_session
from app.users import current_active_user

# from app.utils.blocknote_converter import (
#     convert_blocknote_to_markdown,
#     convert_markdown_to_blocknote,
# )

router = APIRouter()


@router.get("/documents/{document_id}/editor-content")
async def get_editor_content(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get document content for editing.

    Returns BlockNote JSON document. If blocknote_document is NULL,
    attempts to generate it from chunks (lazy migration).
    """
    from sqlalchemy.orm import selectinload
    
    result = await session.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .join(SearchSpace)
        .filter(Document.id == document_id, SearchSpace.user_id == user.id)
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # If blocknote_document exists, return it
    if document.blocknote_document:
        return {
            "document_id": document.id,
            "title": document.title,
            "blocknote_document": document.blocknote_document,
            "last_edited_at": document.last_edited_at.isoformat()
            if document.last_edited_at
            else None,
        }

    # Lazy migration: Try to generate blocknote_document from chunks
    from app.utils.blocknote_converter import convert_markdown_to_blocknote
    
    chunks = sorted(document.chunks, key=lambda c: c.id)
    
    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="This document has no chunks and cannot be edited. Please re-upload to enable editing.",
        )
    
    # Reconstruct markdown from chunks
    markdown_content = "\n\n".join(chunk.content for chunk in chunks)
    
    if not markdown_content.strip():
        raise HTTPException(
            status_code=400,
            detail="This document has empty content and cannot be edited.",
        )
    
    # Convert to BlockNote
    blocknote_json = await convert_markdown_to_blocknote(markdown_content)
    
    if not blocknote_json:
        raise HTTPException(
            status_code=500,
            detail="Failed to convert document to editable format. Please try again later.",
        )
    
    # Save the generated blocknote_document (lazy migration)
    document.blocknote_document = blocknote_json
    document.content_needs_reindexing = False
    document.last_edited_at = None
    await session.commit()
    
    return {
        "document_id": document.id,
        "title": document.title,
        "blocknote_document": blocknote_json,
        "last_edited_at": None,
    }


@router.put("/documents/{document_id}/blocknote-content")
async def update_blocknote_content(
    document_id: int,
    data: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Auto-save BlockNote document during editing.
    Only updates blocknote_document field, not content.
    """
    result = await session.execute(
        select(Document)
        .join(SearchSpace)
        .filter(Document.id == document_id, SearchSpace.user_id == user.id)
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    blocknote_document = data.get("blocknote_document")
    if not blocknote_document:
        raise HTTPException(status_code=400, detail="blocknote_document is required")

    # Update only blocknote_document and last_edited_at
    document.blocknote_document = blocknote_document
    document.last_edited_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(document)

    return {"status": "saved", "last_edited_at": document.last_edited_at.isoformat()}


# did not implement reindexing (for now)
# @router.post("/documents/{document_id}/finalize-edit")
# async def finalize_edit(
#     document_id: int,
#     session: AsyncSession = Depends(get_async_session),
#     user: User = Depends(current_active_user),
# ):
#     """
#     Finalize document editing: convert BlockNote to markdown,
#     update content (summary), and trigger reindexing.
#     """
#     result = await session.execute(
#         select(Document)
#         .join(SearchSpace)
#         .filter(Document.id == document_id, SearchSpace.user_id == user.id)
#     )
#     document = result.scalars().first()

#     if not document:
#         raise HTTPException(status_code=404, detail="Document not found")

#     if not document.blocknote_document:
#         raise HTTPException(
#             status_code=400,
#             detail="Document has no BlockNote content to finalize"
#         )

#     # 1. Convert BlockNote JSON → Markdown
#     full_markdown = await convert_blocknote_to_markdown(document.blocknote_document)

#     if not full_markdown:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to convert BlockNote document to markdown"
#         )

#     # 2. Generate new summary from full markdown
#     from app.services.llm_service import get_user_long_context_llm
#     from app.utils.document_converters import generate_document_summary

#     user_llm = await get_user_long_context_llm(session, str(user.id), document.search_space_id)
#     if not user_llm:
#         raise HTTPException(
#             status_code=500,
#             detail="No LLM configured for summary generation"
#         )

#     document_metadata = document.document_metadata or {}
#     summary_content, summary_embedding = await generate_document_summary(
#         full_markdown, user_llm, document_metadata
#     )

#     # 3. Update document fields
#     document.content = summary_content
#     document.embedding = summary_embedding
#     document.content_needs_reindexing = True  # Trigger chunk regeneration
#     document.last_edited_at = datetime.now(UTC)

#     await session.commit()

#     return {
#         "status": "finalized",
#         "message": "Document saved. Summary and chunks will be regenerated in the background.",
#         "content_needs_reindexing": True,
#     }
