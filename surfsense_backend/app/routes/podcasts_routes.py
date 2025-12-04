import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import (
    Chat,
    Permission,
    Podcast,
    SearchSpace,
    SearchSpaceMembership,
    User,
    get_async_session,
)
from app.schemas import (
    PodcastCreate,
    PodcastGenerateRequest,
    PodcastRead,
    PodcastUpdate,
)
from app.tasks.podcast_tasks import generate_chat_podcast
from app.users import current_active_user
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/podcasts", response_model=PodcastRead)
async def create_podcast(
    podcast: PodcastCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new podcast.
    Requires PODCASTS_CREATE permission.
    """
    try:
        await check_permission(
            session,
            user,
            podcast.search_space_id,
            Permission.PODCASTS_CREATE.value,
            "You don't have permission to create podcasts in this search space",
        )
        db_podcast = Podcast(**podcast.model_dump())
        session.add(db_podcast)
        await session.commit()
        await session.refresh(db_podcast)
        return db_podcast
    except HTTPException as he:
        raise he
    except IntegrityError as e:
        await session.rollback()
        logger.warning("Podcast creation failed due to integrity error: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Podcast creation failed due to constraint violation",
        ) from None
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error("Database error while creating podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Database error occurred while creating podcast"
        ) from None
    except Exception as e:
        await session.rollback()
        logger.error("Unexpected error while creating podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while creating podcast"
        ) from None


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
    except SQLAlchemyError as e:
        logger.error("Database error while fetching podcasts: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching podcasts"
        ) from None
    except Exception as e:
        logger.error("Unexpected error while fetching podcasts: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while fetching podcasts"
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
    except SQLAlchemyError as e:
        logger.error("Database error while fetching podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching podcast"
        ) from None
    except Exception as e:
        logger.error("Unexpected error while fetching podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while fetching podcast"
        ) from None


@router.put("/podcasts/{podcast_id}", response_model=PodcastRead)
async def update_podcast(
    podcast_id: int,
    podcast_update: PodcastUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a podcast.
    Requires PODCASTS_UPDATE permission for the search space.
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
            Permission.PODCASTS_UPDATE.value,
            "You don't have permission to update podcasts in this search space",
        )

        update_data = podcast_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_podcast, key, value)
        await session.commit()
        await session.refresh(db_podcast)
        return db_podcast
    except HTTPException as he:
        raise he
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail="Update failed due to constraint violation"
        ) from None
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error("Database error while updating podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Database error occurred while updating podcast"
        ) from None
    except Exception as e:
        await session.rollback()
        logger.error("Unexpected error while updating podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while updating podcast"
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
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error("Database error while deleting podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Database error occurred while deleting podcast"
        ) from None
    except Exception as e:
        await session.rollback()
        logger.error("Unexpected error while deleting podcast: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred while deleting podcast"
        ) from None


async def generate_chat_podcast_with_new_session(
    chat_id: int,
    search_space_id: int,
    user_id: int,
    podcast_title: str | None = None,
    user_prompt: str | None = None,
):
    """Create a new session and process chat podcast generation."""
    from app.db import async_session_maker

    async with async_session_maker() as session:
        try:
            await generate_chat_podcast(
                session, chat_id, search_space_id, user_id, podcast_title, user_prompt
            )
        except Exception as e:
            logger.error("Error generating podcast from chat: %s", e, exc_info=True)


@router.post("/podcasts/generate")
async def generate_podcast(
    request: PodcastGenerateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Generate a podcast from a chat or document.
    Requires PODCASTS_CREATE permission.
    """
    try:
        # Check if the user has permission to create podcasts
        await check_permission(
            session,
            user,
            request.search_space_id,
            Permission.PODCASTS_CREATE.value,
            "You don't have permission to create podcasts in this search space",
        )

        if request.type == "CHAT":
            # Verify that all chat IDs belong to this user and search space
            query = (
                select(Chat)
                .filter(
                    Chat.id.in_(request.ids),
                    Chat.search_space_id == request.search_space_id,
                )
                .join(SearchSpace)
                .filter(SearchSpace.user_id == user.id)
            )

            result = await session.execute(query)
            valid_chats = result.scalars().all()
            valid_chat_ids = [chat.id for chat in valid_chats]

            # If any requested ID is not in valid IDs, raise error immediately
            if len(valid_chat_ids) != len(request.ids):
                raise HTTPException(
                    status_code=403,
                    detail="One or more chat IDs do not belong to this user or search space",
                )

            from app.tasks.celery_tasks.podcast_tasks import (
                generate_chat_podcast_task,
            )

            # Add Celery tasks for each chat ID
            for chat_id in valid_chat_ids:
                generate_chat_podcast_task.delay(
                    chat_id,
                    request.search_space_id,
                    user.id,
                    request.podcast_title,
                    request.user_prompt,
                )

        return {
            "message": "Podcast generation started",
        }
    except HTTPException as he:
        raise he
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Podcast generation failed due to constraint violation",
        ) from None
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error occurred while generating podcast"
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e!s}"
        ) from e


@router.get("/podcasts/{podcast_id}/stream")
async def stream_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Stream a podcast audio file.
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
            "You don't have permission to access podcasts in this search space",
        )

        # Get the file path
        file_path = podcast.file_location

        # Check if the file exists
        if not os.path.isfile(file_path):
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


@router.get("/podcasts/by-chat/{chat_id}", response_model=PodcastRead | None)
async def get_podcast_by_chat_id(
    chat_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a podcast by its associated chat ID.
    Requires PODCASTS_READ permission for the search space.
    """
    try:
        # First get the chat to find its search space
        chat_result = await session.execute(select(Chat).filter(Chat.id == chat_id))
        chat = chat_result.scalars().first()

        if not chat:
            return None

        # Check permission for the search space
        await check_permission(
            session,
            user,
            chat.search_space_id,
            Permission.PODCASTS_READ.value,
            "You don't have permission to read podcasts in this search space",
        )

        # Get the podcast
        result = await session.execute(
            select(Podcast).filter(Podcast.chat_id == chat_id)
        )
        podcast = result.scalars().first()

        return podcast
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching podcast: {e!s}"
        ) from e
