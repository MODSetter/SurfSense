"""
Editor routes for BlockNote document editing.
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

    Returns BlockNote JSON document. If blocknote_document is NULL,
    attempts to generate it from chunks (lazy migration).

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

    # If blocknote_document exists, return it
    if document.blocknote_document:
        return {
            "document_id": document.id,
            "title": document.title,
            "document_type": document.document_type.value,
            "blocknote_document": document.blocknote_document,
            "updated_at": document.updated_at.isoformat()
            if document.updated_at
            else None,
        }

    # For NOTE type documents, return empty BlockNote structure if no content exists
    if document.document_type == DocumentType.NOTE:
        # Return empty BlockNote structure
        empty_blocknote = [
            {
                "type": "paragraph",
                "content": [],
                "children": [],
            }
        ]
        # Save empty structure if not already saved
        if not document.blocknote_document:
            document.blocknote_document = empty_blocknote
            await session.commit()
        return {
            "document_id": document.id,
            "title": document.title,
            "document_type": document.document_type.value,
            "blocknote_document": empty_blocknote,
            "updated_at": document.updated_at.isoformat()
            if document.updated_at
            else None,
        }

    # Lazy migration: Try to generate blocknote_document from chunks (for other document types)
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
    await session.commit()

    return {
        "document_id": document.id,
        "title": document.title,
        "document_type": document.document_type.value,
        "blocknote_document": blocknote_json,
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
    Save BlockNote document and trigger reindexing.
    Called when user clicks 'Save & Exit'.

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

    blocknote_document = data.get("blocknote_document")
    if not blocknote_document:
        raise HTTPException(status_code=400, detail="blocknote_document is required")

    # Add type validation
    if not isinstance(blocknote_document, list):
        raise HTTPException(status_code=400, detail="blocknote_document must be a list")

    # For NOTE type documents, extract title from first block (heading)
    if (
        document.document_type == DocumentType.NOTE
        and blocknote_document
        and len(blocknote_document) > 0
    ):
        first_block = blocknote_document[0]
        if (
            first_block
            and first_block.get("content")
            and isinstance(first_block["content"], list)
        ):
            # Extract text from first block content
            # Match the frontend extractTitleFromBlockNote logic exactly
            title_parts = []
            for item in first_block["content"]:
                if isinstance(item, str):
                    title_parts.append(item)
                elif (
                    isinstance(item, dict)
                    and "text" in item
                    and isinstance(item["text"], str)
                ):
                    # BlockNote structure: {"type": "text", "text": "...", "styles": {}}
                    title_parts.append(item["text"])

            new_title = "".join(title_parts).strip()
            if new_title:
                document.title = new_title
            else:
                # Only set to "Untitled" if content exists but is empty
                document.title = "Untitled"

    # Save BlockNote document
    document.blocknote_document = blocknote_document
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
