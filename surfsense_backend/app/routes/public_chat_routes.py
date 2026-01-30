"""
Routes for public chat access via immutable snapshots.

All public endpoints use share_token for access - no authentication required
for read operations. Clone requires authentication.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.schemas.new_chat import (
    CloneResponse,
    PublicChatResponse,
)
from app.services.public_chat_service import (
    clone_from_snapshot,
    get_public_chat,
    get_snapshot_podcast,
)
from app.users import current_active_user

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/{share_token}", response_model=PublicChatResponse)
async def read_public_chat(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get a public chat snapshot by share token.

    No authentication required.
    Returns immutable snapshot data (sanitized, citations stripped).
    """
    return await get_public_chat(session, share_token)


@router.post("/{share_token}/clone", response_model=CloneResponse)
async def clone_public_chat(
    share_token: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Clone a public chat snapshot to the user's account.

    Creates thread and copies messages.
    Requires authentication.
    """
    return await clone_from_snapshot(session, share_token, user)


@router.get("/{share_token}/podcasts/{podcast_id}")
async def get_public_podcast(
    share_token: str,
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get podcast details from a public chat snapshot.

    No authentication required - the share_token provides access.
    Returns podcast info including transcript.
    """
    podcast_info = await get_snapshot_podcast(session, share_token, podcast_id)

    if not podcast_info:
        raise HTTPException(status_code=404, detail="Podcast not found")

    return {
        "id": podcast_info.get("original_id"),
        "title": podcast_info.get("title"),
        "status": "ready",
        "podcast_transcript": podcast_info.get("transcript"),
    }


@router.get("/{share_token}/podcasts/{podcast_id}/stream")
async def stream_public_podcast(
    share_token: str,
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stream a podcast from a public chat snapshot.

    No authentication required - the share_token provides access.
    Looks up podcast by original_id in the snapshot's podcasts array.
    """
    podcast_info = await get_snapshot_podcast(session, share_token, podcast_id)

    if not podcast_info:
        raise HTTPException(status_code=404, detail="Podcast not found")

    file_path = podcast_info.get("file_path")

    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Podcast audio file not found")

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type="audio/mpeg",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={os.path.basename(file_path)}",
        },
    )
