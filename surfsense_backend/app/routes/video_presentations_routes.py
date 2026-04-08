"""
Video presentation routes for CRUD operations and per-slide audio streaming.

These routes support the video presentation generation feature in new-chat.
Frontend polls GET /video-presentations/{id} to check status field.
When ready, the slides JSONB contains per-slide Remotion code and audio file paths.
The frontend compiles the Remotion code via Babel and renders with Remotion Player.
"""

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import (
    Permission,
    SearchSpace,
    SearchSpaceMembership,
    User,
    VideoPresentation,
    get_async_session,
)
from app.schemas import VideoPresentationRead
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


@router.get("/video-presentations", response_model=list[VideoPresentationRead])
async def read_video_presentations(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List video presentations the user has access to.
    Requires VIDEO_PRESENTATIONS_READ permission for the search space(s).
    """
    if skip < 0 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")
    try:
        if search_space_id is not None:
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.VIDEO_PRESENTATIONS_READ.value,
                "You don't have permission to read video presentations in this search space",
            )
            result = await session.execute(
                select(VideoPresentation)
                .filter(VideoPresentation.search_space_id == search_space_id)
                .offset(skip)
                .limit(limit)
            )
        else:
            result = await session.execute(
                select(VideoPresentation)
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .offset(skip)
                .limit(limit)
            )
        return [
            VideoPresentationRead.from_orm_with_slides(vp)
            for vp in result.scalars().all()
        ]
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching video presentations",
        ) from None


@router.get(
    "/video-presentations/{video_presentation_id}",
    response_model=VideoPresentationRead,
)
async def read_video_presentation(
    video_presentation_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific video presentation by ID.
    Requires authentication with VIDEO_PRESENTATIONS_READ permission.

    When status is "ready", the response includes:
    - slides: parsed slide data with per-slide audio_url and durations
    - scene_codes: Remotion component source code per slide
    """
    try:
        result = await session.execute(
            select(VideoPresentation).filter(
                VideoPresentation.id == video_presentation_id
            )
        )
        video_pres = result.scalars().first()

        if not video_pres:
            raise HTTPException(status_code=404, detail="Video presentation not found")

        await check_permission(
            session,
            user,
            video_pres.search_space_id,
            Permission.VIDEO_PRESENTATIONS_READ.value,
            "You don't have permission to read video presentations in this search space",
        )

        return VideoPresentationRead.from_orm_with_slides(video_pres)
    except HTTPException as he:
        raise he
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while fetching video presentation",
        ) from None


@router.delete("/video-presentations/{video_presentation_id}", response_model=dict)
async def delete_video_presentation(
    video_presentation_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a video presentation.
    Requires VIDEO_PRESENTATIONS_DELETE permission for the search space.
    """
    try:
        result = await session.execute(
            select(VideoPresentation).filter(
                VideoPresentation.id == video_presentation_id
            )
        )
        db_video_pres = result.scalars().first()

        if not db_video_pres:
            raise HTTPException(status_code=404, detail="Video presentation not found")

        await check_permission(
            session,
            user,
            db_video_pres.search_space_id,
            Permission.VIDEO_PRESENTATIONS_DELETE.value,
            "You don't have permission to delete video presentations in this search space",
        )

        await session.delete(db_video_pres)
        await session.commit()
        return {"message": "Video presentation deleted successfully"}
    except HTTPException as he:
        raise he
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Database error occurred while deleting video presentation",
        ) from None


@router.get("/video-presentations/{video_presentation_id}/slides/{slide_number}/audio")
async def stream_slide_audio(
    video_presentation_id: int,
    slide_number: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Stream the audio file for a specific slide in a video presentation.
    The slide_number is 1-based. Audio path is read from the slides JSONB.
    """
    try:
        result = await session.execute(
            select(VideoPresentation).filter(
                VideoPresentation.id == video_presentation_id
            )
        )
        video_pres = result.scalars().first()

        if not video_pres:
            raise HTTPException(status_code=404, detail="Video presentation not found")

        await check_permission(
            session,
            user,
            video_pres.search_space_id,
            Permission.VIDEO_PRESENTATIONS_READ.value,
            "You don't have permission to access video presentations in this search space",
        )

        slides = video_pres.slides or []
        slide_data = None
        for s in slides:
            if s.get("slide_number") == slide_number:
                slide_data = s
                break

        if not slide_data:
            raise HTTPException(
                status_code=404,
                detail=f"Slide {slide_number} not found",
            )

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

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error streaming slide audio: {e!s}",
        ) from e
