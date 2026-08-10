"""Authenticated streaming for immutable generated document files."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import Permission, get_async_session
from app.file_storage.persistence.models import DocumentFile
from app.file_storage.service import open_document_file_stream
from app.users import get_auth_context
from app.utils.rbac import check_permission

router = APIRouter()


def _content_disposition(filename: str, *, inline: bool) -> str:
    fallback = filename.encode("ascii", "ignore").decode("ascii") or "download"
    fallback = fallback.replace('"', "").replace("\r", "").replace("\n", "")
    mode = "inline" if inline else "attachment"
    return f"{mode}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def _is_inline(mime_type: str) -> bool:
    # Stored files are user- or agent-authored, so rendering one on our origin
    # is an XSS grant. Only PDF has a sandboxed native viewer; everything else
    # downloads. Widen per MIME type, by name with a consumer attached — never
    # by wildcard (image/* once smuggled in scriptable SVG).
    return mime_type == "application/pdf"


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
            DocumentFile.role != "source",
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
