"""
Editor routes for document editing with markdown (Plate.js frontend).
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Document, DocumentType, Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


@router.get("/search-spaces/{search_space_id}/documents/{document_id}/editor-content")
async def get_editor_content(
    search_space_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get document content for editing.

    Returns source_markdown for the Plate.js editor.
    Falls back to blocknote_document → markdown conversion, then chunk reconstruction.

    Requires DOCUMENTS_READ permission.
    """
    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this search space",
    )

    result = await session.execute(
        select(Document)
        .options(selectinload(Document.chunks))
        .filter(
            Document.id == document_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Priority 1: Return source_markdown if it exists (check `is not None` to allow empty strings)
    if document.source_markdown is not None:
        return {
            "document_id": document.id,
            "title": document.title,
            "document_type": document.document_type.value,
            "source_markdown": document.source_markdown,
            "updated_at": document.updated_at.isoformat()
            if document.updated_at
            else None,
        }

    # Priority 2: Lazy-migrate from blocknote_document (pure Python, no external deps)
    if document.blocknote_document:
        from app.utils.blocknote_to_markdown import blocknote_to_markdown

        markdown = blocknote_to_markdown(document.blocknote_document)
        if markdown:
            # Persist the migration so we don't repeat it
            document.source_markdown = markdown
            await session.commit()
            return {
                "document_id": document.id,
                "title": document.title,
                "document_type": document.document_type.value,
                "source_markdown": markdown,
                "updated_at": document.updated_at.isoformat()
                if document.updated_at
                else None,
            }

    # Priority 3: For NOTE type with no content, return empty markdown
    if document.document_type == DocumentType.NOTE:
        empty_markdown = ""
        document.source_markdown = empty_markdown
        await session.commit()
        return {
            "document_id": document.id,
            "title": document.title,
            "document_type": document.document_type.value,
            "source_markdown": empty_markdown,
            "updated_at": document.updated_at.isoformat()
            if document.updated_at
            else None,
        }

    # Priority 4: Reconstruct from chunks
    chunks = sorted(document.chunks, key=lambda c: c.id)

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="This document has no content and cannot be edited. Please re-upload to enable editing.",
        )

    markdown_content = "\n\n".join(chunk.content for chunk in chunks)

    if not markdown_content.strip():
        raise HTTPException(
            status_code=400,
            detail="This document has empty content and cannot be edited.",
        )

    # Persist the lazy migration
    document.source_markdown = markdown_content
    await session.commit()

    return {
        "document_id": document.id,
        "title": document.title,
        "document_type": document.document_type.value,
        "source_markdown": markdown_content,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


@router.post("/search-spaces/{search_space_id}/documents/{document_id}/save")
async def save_document(
    search_space_id: int,
    document_id: int,
    data: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Save document markdown and trigger reindexing.
    Called when user clicks 'Save & Exit'.

    Accepts { "source_markdown": "...", "title": "..." (optional) }.

    Requires DOCUMENTS_UPDATE permission.
    """
    from app.tasks.celery_tasks.document_reindex_tasks import reindex_document_task

    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_UPDATE.value,
        "You don't have permission to update documents in this search space",
    )

    result = await session.execute(
        select(Document).filter(
            Document.id == document_id,
            Document.search_space_id == search_space_id,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    source_markdown = data.get("source_markdown")
    if source_markdown is None:
        raise HTTPException(status_code=400, detail="source_markdown is required")

    if not isinstance(source_markdown, str):
        raise HTTPException(status_code=400, detail="source_markdown must be a string")

    # For NOTE type, extract title from first heading line if present
    if document.document_type == DocumentType.NOTE:
        # If the frontend sends a title, use it; otherwise extract from markdown
        new_title = data.get("title")
        if not new_title:
            # Extract title from the first line of markdown (# Heading)
            for line in source_markdown.split("\n"):
                stripped = line.strip()
                if stripped.startswith("# "):
                    new_title = stripped[2:].strip()
                    break
                elif stripped:
                    # First non-empty non-heading line
                    new_title = stripped[:100]
                    break

        if new_title:
            document.title = new_title.strip()
        else:
            document.title = "Untitled"

    # Save source_markdown
    document.source_markdown = source_markdown
    document.updated_at = datetime.now(UTC)
    document.content_needs_reindexing = True

    await session.commit()

    # Queue reindex task
    reindex_document_task.delay(document_id, str(user.id))

    return {
        "status": "saved",
        "document_id": document_id,
        "message": "Document saved and will be reindexed in the background",
        "updated_at": document.updated_at.isoformat(),
    }
