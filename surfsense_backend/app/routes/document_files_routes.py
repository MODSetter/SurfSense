"""Authenticated streaming for immutable document files."""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Document, Permission, get_async_session
from app.file_storage.persistence.enums import DocumentFileKind
from app.file_storage.persistence.models import DocumentFile
from app.file_storage.schemas import DocumentViewFileRead, DocumentViewManifestRead
from app.file_storage.service import get_document_file, open_document_file_stream
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()

_ORIGINAL_VIEW_MIME_BY_SUFFIX = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _content_disposition(filename: str, *, inline: bool) -> str:
    fallback = filename.encode("ascii", "ignore").decode("ascii") or "download"
    fallback = fallback.replace('"', "").replace("\r", "").replace("\n", "")
    mode = "inline" if inline else "attachment"
    return f"{mode}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def _is_inline(mime_type: str) -> bool:
    # Stored files are user- or agent-authored, so rendering one on our origin
    # is an XSS grant. PDF and MP4 have constrained native viewers; everything
    # else downloads. Widen per MIME type, by name with a consumer attached — never
    # by wildcard (image/* once smuggled in scriptable SVG).
    return mime_type in {"application/pdf", "video/mp4"}


def _canonical_original_mime(filename: str, stored_mime: str | None) -> str | None:
    """Return a MIME supported by the original-file viewers, including legacy rows."""
    by_suffix = _ORIGINAL_VIEW_MIME_BY_SUFFIX.get(
        PurePosixPath(filename).suffix.lower()
    )
    if by_suffix is not None:
        return by_suffix
    if stored_mime in _ORIGINAL_VIEW_MIME_BY_SUFFIX.values():
        return stored_mime
    return None


@router.get(
    "/workspaces/{workspace_id}/documents/{document_id}/view-manifest",
    response_model=DocumentViewManifestRead,
)
async def get_document_view_manifest(
    workspace_id: int,
    document_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> DocumentViewManifestRead:
    """Describe how a knowledge document should open without returning its text."""
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )
    document = await session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    original = await get_document_file(
        session,
        document_id=document_id,
        kind=DocumentFileKind.ORIGINAL,
    )
    candidate_filename = (
        original.original_filename if original is not None else document.title
    )
    canonical_mime = _canonical_original_mime(
        candidate_filename,
        original.mime_type if original is not None else None,
    )
    status = (
        document.status.get("state", "ready")
        if isinstance(document.status, dict)
        else "ready"
    )
    document_type = (
        document.document_type.value
        if hasattr(document.document_type, "value")
        else str(document.document_type)
    )
    view_file = (
        DocumentViewFileRead(
            file_id=original.id,
            filename=original.original_filename,
            mime_type=canonical_mime
            or original.mime_type
            or "application/octet-stream",
            size_bytes=original.size_bytes,
            content_url=(
                f"/api/v1/workspaces/{workspace_id}/documents/{document_id}/"
                f"files/{original.id}/content"
            ),
        )
        if original is not None
        else None
    )

    if canonical_mime is None:
        return DocumentViewManifestRead(
            document_id=document.id,
            title=document.title,
            document_type=document_type,
            status=status,
            presentation="text",
            file=view_file,
        )
    if original is None:
        return DocumentViewManifestRead(
            document_id=document.id,
            title=document.title,
            document_type=document_type,
            status=status,
            presentation="missing_original",
        )
    return DocumentViewManifestRead(
        document_id=document.id,
        title=document.title,
        document_type=document_type,
        status=status,
        presentation="original",
        file=view_file,
    )


@router.get(
    "/workspaces/{workspace_id}/documents/{document_id}/files/{file_id}/content"
)
async def stream_document_file(
    workspace_id: int,
    document_id: int,
    file_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    await check_permission(
        session,
        auth,
        workspace_id,
        Permission.DOCUMENTS_READ.value,
        "You don't have permission to read documents in this workspace",
    )
    record = await session.scalar(
        select(DocumentFile).where(
            DocumentFile.id == file_id,
            DocumentFile.document_id == document_id,
            DocumentFile.workspace_id == workspace_id,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Document file not found")

    etag = f'"{record.checksum_sha256}"'
    cache_headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)

    mime_type = record.mime_type or "application/octet-stream"
    return StreamingResponse(
        open_document_file_stream(record),
        media_type=mime_type,
        headers={
            **cache_headers,
            "Content-Disposition": _content_disposition(
                record.original_filename,
                inline=_is_inline(mime_type),
            ),
        },
    )
