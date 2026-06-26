"""HTTP routes for document file storage (metadata listing + original download)."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Document, Permission, get_async_session
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.schemas import DocumentFileRead
from app.file_storage.service import (
    get_document_file,
    list_document_files,
    open_document_file_stream,
)
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


async def _load_readable_document(
    *, document_id: int, session: AsyncSession, auth: AuthContext
) -> Document:
    """Load a document the user may read, or raise 404/403."""
    document = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    await check_permission(
        session,
        auth,
        document.workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )
    return document


def _content_disposition(filename: str) -> str:
    """Build an attachment header safe for arbitrary filenames (RFC 5987)."""
    fallback = filename.encode("ascii", "ignore").decode("ascii") or "download"
    fallback = fallback.replace('"', "")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.get(
    "/documents/{document_id}/files",
    response_model=list[DocumentFileRead],
)
async def read_document_files(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[DocumentFileRead]:
    """Return metadata for every stored file of a document (gates the UI)."""
    await _load_readable_document(document_id=document_id, session=session, auth=auth)
    records = await list_document_files(session, document_id=document_id)
    return [DocumentFileRead.model_validate(r) for r in records]


@router.get("/documents/{document_id}/download-original")
async def download_original_document_file(
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    """Stream the document's original uploaded file."""
    await _load_readable_document(document_id=document_id, session=session, auth=auth)

    record = await get_document_file(
        session, document_id=document_id, kind=DocumentFileKind.ORIGINAL
    )
    if record is None:
        raise HTTPException(
            status_code=404, detail="No original file stored for this document"
        )

    return StreamingResponse(
        open_document_file_stream(record),
        media_type=record.mime_type or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(record.original_filename)},
    )
