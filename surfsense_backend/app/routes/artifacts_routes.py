"""Workspace-scoped artifact manifests, files, downloads, and lifecycle."""

from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.artifacts.persistence import (
    Artifact,
    ArtifactFile,
    ArtifactFileRole,
)
from app.artifacts.storage import open_artifact_file_stream
from app.auth.context import AuthContext
from app.db import Document, Permission, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

from .document_files_routes import _content_disposition, _is_inline

router = APIRouter()


def _markdown_filename(title: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in " -_" else "_"
        for character in title
    ).strip()[:80]
    return f"{safe or 'artifact'}.md"


async def _authorize_artifact(
    session: AsyncSession,
    auth: AuthContext,
    workspace_id: int,
    permission: Permission,
    action: str,
) -> None:
    await check_permission(
        session,
        auth,
        workspace_id,
        permission.value,
        f"You don't have permission to {action} artifacts in this workspace",
    )


def _visible_files(artifact: Artifact) -> list[ArtifactFile]:
    return sorted(
        (file for file in artifact.files if file.role is not ArtifactFileRole.SOURCE),
        key=lambda item: (item.role is not ArtifactFileRole.PRIMARY, item.id),
    )


def _file_manifest(
    workspace_id: int, artifact_id: int, record: ArtifactFile
) -> dict[str, object]:
    return {
        "file_id": record.id,
        "role": record.role.value,
        "filename": record.original_filename,
        "mime_type": record.mime_type or "application/octet-stream",
        "size_bytes": record.size_bytes,
        "content_url": (
            f"/api/v1/workspaces/{workspace_id}/artifacts/"
            f"{artifact_id}/files/{record.id}/content"
        ),
    }


@router.get("/workspaces/{workspace_id}/artifacts")
async def list_artifacts(
    workspace_id: int,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    rows = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .where(Artifact.workspace_id == workspace_id)
            .order_by(Artifact.updated_at.desc(), Artifact.id.desc())
        )
    ).all()
    response.headers["Cache-Control"] = "private, no-store"
    return [
        {
            "artifact_id": artifact.id,
            "title": document.title,
            "format": artifact.format,
            "generation": artifact.generation,
            "indexing_status": (document.status or {}).get("state", "ready"),
            "thread_id": artifact.thread_id,
            "created_at": artifact.created_at.isoformat(),
            "updated_at": (
                artifact.updated_at.isoformat() if artifact.updated_at else None
            ),
        }
        for artifact, document in rows
    ]


@router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/manifest")
async def get_artifact_manifest(
    workspace_id: int,
    artifact_id: int,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .options(selectinload(Artifact.files))
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact, document = row
    etag = f'"{document.content_hash}:{artifact.generation}"'
    cache_headers = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)
    response.headers.update(cache_headers)
    return {
        "artifact_id": artifact.id,
        "document_id": document.id,
        "title": document.title,
        "format": artifact.format,
        "generation": artifact.generation,
        "markdown_representation": document.source_markdown or document.content,
        "files": [
            _file_manifest(workspace_id, artifact.id, file)
            for file in _visible_files(artifact)
        ],
        "updated_at": (
            artifact.updated_at.isoformat() if artifact.updated_at else None
        ),
    }


@router.get("/workspaces/{workspace_id}/artifacts/{artifact_id}/download")
async def download_artifact(
    workspace_id: int,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> StreamingResponse:
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .options(selectinload(Artifact.files))
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    artifact, document = row
    primary = next(
        (file for file in artifact.files if file.role is ArtifactFileRole.PRIMARY),
        None,
    )
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    if primary is not None:
        return StreamingResponse(
            open_artifact_file_stream(primary),
            media_type=primary.mime_type or "application/octet-stream",
            headers={
                **headers,
                "Content-Disposition": _content_disposition(
                    primary.original_filename, inline=False
                ),
            },
        )
    filename = _markdown_filename(document.title)
    return StreamingResponse(
        io.BytesIO((document.source_markdown or document.content).encode()),
        media_type="text/markdown; charset=utf-8",
        headers={
            **headers,
            "Content-Disposition": _content_disposition(filename, inline=False),
        },
    )


@router.delete("/workspaces/{workspace_id}/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    workspace_id: int,
    artifact_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_DELETE, "delete"
    )
    row = (
        await session.execute(
            select(Artifact, Document)
            .join(Document, Artifact.document_id == Document.id)
            .where(Artifact.id == artifact_id, Artifact.workspace_id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    _, document = row

    document.status = {"state": "deleting"}
    await session.commit()
    try:
        from app.tasks.celery_tasks.document_tasks import delete_document_task

        delete_document_task.delay(document.id)
    except Exception as dispatch_error:
        document.status = {"state": "ready"}
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail="Failed to queue background deletion. Please try again.",
        ) from dispatch_error
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.get(
    "/workspaces/{workspace_id}/artifacts/{artifact_id}/files/{file_id}/content"
)
async def stream_artifact_file(
    workspace_id: int,
    artifact_id: int,
    file_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> Response:
    await _authorize_artifact(
        session, auth, workspace_id, Permission.ARTIFACTS_READ, "read"
    )
    record = await session.scalar(
        select(ArtifactFile)
        .join(Artifact, ArtifactFile.artifact_id == Artifact.id)
        .where(
            ArtifactFile.id == file_id,
            ArtifactFile.artifact_id == artifact_id,
            Artifact.workspace_id == workspace_id,
            ArtifactFile.role != ArtifactFileRole.SOURCE,
        )
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Artifact file not found")

    etag_value = record.checksum_sha256 or f"artifact-file-{record.id}"
    etag = f'"{etag_value}"'
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=31536000, immutable",
        "X-Content-Type-Options": "nosniff",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    mime_type = record.mime_type or "application/octet-stream"
    return StreamingResponse(
        open_artifact_file_stream(record),
        media_type=mime_type,
        headers={
            **headers,
            "Content-Disposition": _content_disposition(
                record.original_filename, inline=_is_inline(mime_type)
            ),
        },
    )
