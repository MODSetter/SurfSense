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
    get_snapshot_report,
    get_snapshot_video_presentation,
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


@router.get("/{share_token}/video-presentations/{video_presentation_id}")
async def get_public_video_presentation(
    share_token: str,
    video_presentation_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get video presentation details from a public chat snapshot.

    No authentication required - the share_token provides access.
    Returns slide data (with public audio URLs) and scene codes.
    """
    vp_info = await get_snapshot_video_presentation(
        session, share_token, video_presentation_id
    )

    if not vp_info:
        raise HTTPException(status_code=404, detail="Video presentation not found")

    slides = vp_info.get("slides") or []
    public_slides = _replace_audio_paths_with_public_urls(
        share_token, video_presentation_id, slides
    )

    return {
        "id": vp_info.get("original_id"),
        "title": vp_info.get("title"),
        "status": "ready",
        "slides": public_slides,
        "scene_codes": vp_info.get("scene_codes"),
        "slide_count": len(slides) if slides else None,
    }


@router.get(
    "/{share_token}/video-presentations/{video_presentation_id}/slides/{slide_number}/audio"
)
async def stream_public_slide_audio(
    share_token: str,
    video_presentation_id: int,
    slide_number: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Stream a slide's audio from a public chat snapshot.

    No authentication required - the share_token provides access.
    """
    from pathlib import Path

    vp_info = await get_snapshot_video_presentation(
        session, share_token, video_presentation_id
    )

    if not vp_info:
        raise HTTPException(status_code=404, detail="Video presentation not found")

    slides = vp_info.get("slides") or []
    slide_data = None
    for s in slides:
        if s.get("slide_number") == slide_number:
            slide_data = s
            break

    if not slide_data:
        raise HTTPException(status_code=404, detail=f"Slide {slide_number} not found")

    file_path = slide_data.get("audio_file")
    if not file_path or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Slide audio file not found")

    ext = Path(file_path).suffix.lower()
    media_type = "audio/wav" if ext == ".wav" else "audio/mpeg"

    def iterfile():
        with open(file_path, mode="rb") as file_like:
            yield from file_like

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"inline; filename={Path(file_path).name}",
        },
    )


def _replace_audio_paths_with_public_urls(
    share_token: str,
    video_presentation_id: int,
    slides: list[dict],
) -> list[dict]:
    """Replace server-local audio_file paths with public streaming API URLs."""
    result = []
    for slide in slides:
        slide_copy = dict(slide)
        slide_number = slide_copy.get("slide_number")
        audio_file = slide_copy.pop("audio_file", None)

        if audio_file and slide_number is not None:
            slide_copy["audio_url"] = (
                f"/api/v1/public/{share_token}"
                f"/video-presentations/{video_presentation_id}"
                f"/slides/{slide_number}/audio"
            )
        else:
            slide_copy["audio_url"] = None

        result.append(slide_copy)
    return result


@router.get("/{share_token}/reports/{report_id}/content")
async def get_public_report_content(
    share_token: str,
    report_id: int,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get report content from a public chat snapshot.

    No authentication required - the share_token provides access.
    Returns report content including title, markdown body, metadata, and versions.
    """
    from app.services.public_chat_service import get_snapshot_report_versions

    report_info = await get_snapshot_report(session, share_token, report_id)

    if not report_info:
        raise HTTPException(status_code=404, detail="Report not found")

    # Get version siblings from the same snapshot
    versions = await get_snapshot_report_versions(
        session, share_token, report_info.get("report_group_id")
    )

    return {
        "id": report_info.get("original_id"),
        "title": report_info.get("title"),
        "content": report_info.get("content"),
        "report_metadata": report_info.get("report_metadata"),
        "report_group_id": report_info.get("report_group_id"),
        "versions": versions,
    }
