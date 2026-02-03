"""
Notes routes for creating and managing BlockNote documents.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentType, Permission, User, get_async_session
from app.schemas import DocumentRead, PaginatedResponse
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


class CreateNoteRequest(BaseModel):
    title: str
    blocknote_document: list[dict[str, Any]] | None = None


@router.post("/search-spaces/{search_space_id}/notes", response_model=DocumentRead)
async def create_note(
    search_space_id: int,
    request: CreateNoteRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new note (BlockNote document).

    Requires DOCUMENTS_CREATE permission.
    """
    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_CREATE.value,
        "You don't have permission to create notes in this search space",
    )

    if not request.title or not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")

    # Default empty BlockNote structure if not provided
    blocknote_document = request.blocknote_document
    if blocknote_document is None:
        blocknote_document = [
            {
                "type": "paragraph",
                "content": [],
                "children": [],
            }
        ]

    # Generate content hash (use title for now, will be updated on save)
    import hashlib

    content_hash = hashlib.sha256(request.title.encode()).hexdigest()

    # Create document with NOTE type

    document = Document(
        search_space_id=search_space_id,
        title=request.title.strip(),
        document_type=DocumentType.NOTE,
        content="",  # Empty initially, will be populated on first save/reindex
        content_hash=content_hash,
        blocknote_document=blocknote_document,
        content_needs_reindexing=False,  # Will be set to True on first save
        document_metadata={"NOTE": True},
        embedding=None,  # Will be generated on first reindex
        updated_at=datetime.now(UTC),
        created_by_id=user.id,  # Track who created this note
    )

    session.add(document)
    await session.commit()
    await session.refresh(document)

    return DocumentRead(
        id=document.id,
        title=document.title,
        document_type=document.document_type,
        content=document.content,
        content_hash=document.content_hash,
        unique_identifier_hash=document.unique_identifier_hash,
        document_metadata=document.document_metadata,
        search_space_id=document.search_space_id,
        created_at=document.created_at,
        updated_at=document.updated_at,
        created_by_id=document.created_by_id,
    )


@router.get(
    "/search-spaces/{search_space_id}/notes",
    response_model=PaginatedResponse[DocumentRead],
)
async def list_notes(
    search_space_id: int,
    skip: int | None = None,
    page: int | None = None,
    page_size: int = 50,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all notes in a search space.

    Requires DOCUMENTS_READ permission.
    """
    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read notes in this search space",
    )

    from sqlalchemy import func

    # Build query
    query = select(Document).where(
        Document.search_space_id == search_space_id,
        Document.document_type == DocumentType.NOTE,
    )

    # Get total count
    count_query = select(func.count()).select_from(
        select(Document)
        .where(
            Document.search_space_id == search_space_id,
            Document.document_type == DocumentType.NOTE,
        )
        .subquery()
    )
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    if skip is not None:
        query = query.offset(skip)
    elif page is not None:
        query = query.offset(page * page_size)
    else:
        query = query.offset(0)

    if page_size > 0:
        query = query.limit(page_size)

    # Order by updated_at descending (most recent first)
    query = query.order_by(Document.updated_at.desc())

    # Execute query
    result = await session.execute(query)
    documents = result.scalars().all()

    # Convert to response models
    items = [
        DocumentRead(
            id=doc.id,
            title=doc.title,
            document_type=doc.document_type,
            content=doc.content,
            content_hash=doc.content_hash,
            unique_identifier_hash=doc.unique_identifier_hash,
            document_metadata=doc.document_metadata,
            search_space_id=doc.search_space_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in documents
    ]

    # Calculate pagination info
    actual_skip = (
        skip if skip is not None else (page * page_size if page is not None else 0)
    )
    has_more = (actual_skip + len(items)) < total if page_size > 0 else False

    return PaginatedResponse(
        items=items,
        total=total,
        page=page
        if page is not None
        else (actual_skip // page_size if page_size > 0 else 0),
        page_size=page_size,
        has_more=has_more,
    )


@router.delete("/search-spaces/{search_space_id}/notes/{note_id}")
async def delete_note(
    search_space_id: int,
    note_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a note.

    Requires DOCUMENTS_DELETE permission.
    """
    # Check RBAC permission
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.DOCUMENTS_DELETE.value,
        "You don't have permission to delete notes in this search space",
    )

    # Get document
    result = await session.execute(
        select(Document).where(
            Document.id == note_id,
            Document.search_space_id == search_space_id,
            Document.document_type == DocumentType.NOTE,
        )
    )
    document = result.scalars().first()

    if not document:
        raise HTTPException(status_code=404, detail="Note not found")

    # Delete document (chunks will be cascade deleted)
    await session.delete(document)
    await session.commit()

    return {"message": "Note deleted successfully", "note_id": note_id}
