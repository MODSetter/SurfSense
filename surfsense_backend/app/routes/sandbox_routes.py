"""Routes for downloading files from Daytona sandbox environments."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.auth.context import AuthContext
from app.db import NewChatThread, Permission, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()

MIME_TYPES: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".json": "application/json",
    ".txt": "text/plain",
    ".html": "text/html",
    ".md": "text/markdown",
    ".py": "text/x-python",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
}


def _guess_media_type(filename: str) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    return MIME_TYPES.get(ext, "application/octet-stream")


@router.get("/threads/{thread_id}/sandbox/download")
async def download_sandbox_file(
    thread_id: int,
    path: str = Query(..., description="Absolute path of the file inside the sandbox"),
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Download a file from the Daytona sandbox associated with a chat thread."""

    from app.sandbox import is_sandbox_enabled

    if not is_sandbox_enabled():
        raise HTTPException(status_code=404, detail="Sandbox is not enabled")

    result = await session.execute(
        select(NewChatThread).filter(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await check_permission(
        session,
        auth,
        thread.workspace_id,
        Permission.CHATS_READ.value,
        "You don't have permission to access files in this thread",
    )

    from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.sandbox import (
        get_local_sandbox_file,
    )

    # Prefer locally-persisted copy (sandbox may already be deleted)
    local_content = get_local_sandbox_file(thread_id, path)
    if local_content is not None:
        filename = path.rsplit("/", 1)[-1] if "/" in path else path
        media_type = _guess_media_type(filename)
        return Response(
            content=local_content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Fall back to the live sandbox. After a backend restart the registry cache
    # is empty, so get_session lets the provider rediscover it by thread
    # metadata. If none exists it may create an empty replacement; terminate
    # that replacement when the read proves the file is absent.
    from app.sandbox import get_registry

    registry = await get_registry()
    live = registry.get_cached(thread_id)
    adopted_or_created = live is None
    if live is None:
        try:
            live = await registry.get_session(thread_id, thread.workspace_id)
        except Exception as exc:
            raise HTTPException(
                status_code=404, detail="File is no longer available"
            ) from exc

    try:
        content: bytes = await live.read_file(path)
    except Exception as exc:
        if adopted_or_created:
            await registry.terminate(thread_id)
        logger.warning("Sandbox file download failed for %s: %s", path, exc)
        raise HTTPException(
            status_code=404, detail=f"Could not download file: {exc}"
        ) from exc

    filename = path.rsplit("/", 1)[-1] if "/" in path else path
    media_type = _guess_media_type(filename)

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
