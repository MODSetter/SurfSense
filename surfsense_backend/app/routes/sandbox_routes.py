"""Routes for downloading files from Daytona sandbox environments."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import NewChatThread, Permission, User, get_async_session
from app.users import current_active_user
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
    user: User = Depends(current_active_user),
):
    """Download a file from the Daytona sandbox associated with a chat thread."""

    from app.agents.new_chat.sandbox import get_or_create_sandbox, is_sandbox_enabled

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
        user,
        thread.search_space_id,
        Permission.CHATS_READ.value,
        "You don't have permission to access files in this thread",
    )

    from app.agents.new_chat.sandbox import get_local_sandbox_file

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

    # Fall back to live sandbox download
    try:
        sandbox = await get_or_create_sandbox(thread_id)
        raw_sandbox = sandbox._sandbox
        content: bytes = await asyncio.to_thread(raw_sandbox.fs.download_file, path)
    except Exception as exc:
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
