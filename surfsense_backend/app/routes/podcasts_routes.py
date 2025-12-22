"""
Podcast routes for task status polling and audio retrieval.

These routes support the podcast generation feature in new-chat.
Note: The old Chat-based podcast generation has been removed.
"""

import os
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db import (
    Permission,
    Podcast,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.schemas import PodcastRead
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


@router.get("/podcasts", response_model=list[PodcastRead])
async def read_podcasts(
    skip: int = 0,
    limit: int = 100,
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List podcasts the user has access to.
    Requires PODCASTS_READ permission for the search space(s).
    """
    if skip < 0 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")
    try:
        if search_space_id is not None:
            # Check permission for specific search space
            await check_permission(
                session,
                user,
                search_space_id,
                Permission.PODCASTS_READ.value,
                "You don't have permission to read podcasts in this search space",
            )
            result = await session.execute(
                select(Podcast)
                .filter(Podcast.search_space_id == search_space_id)
                .offset(skip)
                .limit(limit)
            )
        else:
            # Get podcasts from all search spaces user has membership in
            result = await session.execute(
                select(Podcast)
                .join(SearchSpace)
                .join(SearchSpaceMembership)
                .filter(SearchSpaceMembership.user_id == user.id)
                .offset(skip)
                .limit(limit)
            )
        return result.scalars().all()
    except HTTPException:
        raise
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching podcasts"
        ) from None


@router.get("/podcasts/{podcast_id}", response_model=PodcastRead)
async def read_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a specific podcast by ID.
    Requires PODCASTS_READ permission for the search space.
    """
    try:
        result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
        podcast = result.scalars().first()

        if not podcast:
            raise HTTPException(
                status_code=404,
                detail="Podcast not found",
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            podcast.search_space_id,
            Permission.PODCASTS_READ.value,
            "You don't have permission to read podcasts in this search space",
        )

        return podcast
    except HTTPException as he:
        raise he
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching podcast"
        ) from None


@router.delete("/podcasts/{podcast_id}", response_model=dict)
async def delete_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a podcast.
    Requires PODCASTS_DELETE permission for the search space.
    """
    try:
        result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
        db_podcast = result.scalars().first()

        if not db_podcast:
            raise HTTPException(status_code=404, detail="Podcast not found")

        # Check permission for the search space
        await check_permission(
            session,
            user,
            db_podcast.search_space_id,
            Permission.PODCASTS_DELETE.value,
            "You don't have permission to delete podcasts in this search space",
        )

        await session.delete(db_podcast)
        await session.commit()
        return {"message": "Podcast deleted successfully"}
    except HTTPException as he:
        raise he
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error occurred while deleting podcast"
        ) from None


@router.get("/podcasts/{podcast_id}/stream")
@router.get("/podcasts/{podcast_id}/audio")
async def stream_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Stream a podcast audio file.
    Requires PODCASTS_READ permission for the search space.

    Note: Both /stream and /audio endpoints are supported for compatibility.
    """
    try:
        result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
        podcast = result.scalars().first()

        if not podcast:
            raise HTTPException(
                status_code=404,
                detail="Podcast not found",
            )

        # Check permission for the search space
        await check_permission(
            session,
            user,
            podcast.search_space_id,
            Permission.PODCASTS_READ.value,
            "You don't have permission to access podcasts in this search space",
        )

        # Get the file path
        file_path = podcast.file_location

        # Check if the file exists
        if not file_path or not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="Podcast audio file not found")

        # Define a generator function to stream the file
        def iterfile():
            with open(file_path, mode="rb") as file_like:
                yield from file_like

        # Return a streaming response with appropriate headers
        return StreamingResponse(
            iterfile(),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Disposition": f"inline; filename={Path(file_path).name}",
            },
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error streaming podcast: {e!s}"
        ) from e


@router.get("/podcasts/task/{task_id}/status")
async def get_podcast_task_status(
    task_id: str,
    user: User = Depends(current_active_user),
):
    """
    Get the status of a podcast generation task.
    Used by new-chat frontend to poll for completion.

    Returns:
    - status: "processing" | "success" | "error"
    - podcast_id: (only if status == "success")
    - title: (only if status == "success")
    - error: (only if status == "error")
    """
    try:
        result = AsyncResult(task_id, app=celery_app)

        if result.ready():
            # Task completed
            if result.successful():
                task_result = result.result
                if isinstance(task_result, dict):
                    if task_result.get("status") == "success":
                        return {
                            "status": "success",
                            "podcast_id": task_result.get("podcast_id"),
                            "title": task_result.get("title"),
                            "transcript_entries": task_result.get("transcript_entries"),
                        }
                    else:
                        return {
                            "status": "error",
                            "error": task_result.get("error", "Unknown error"),
                        }
                else:
                    return {
                        "status": "error",
                        "error": "Unexpected task result format",
                    }
            else:
                # Task failed
                return {
                    "status": "error",
                    "error": str(result.result) if result.result else "Task failed",
                }
        else:
            # Task still processing
            return {
                "status": "processing",
                "state": result.state,
            }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error checking task status: {e!s}"
        ) from e
