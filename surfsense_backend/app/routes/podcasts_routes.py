import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import Chat, Podcast, SearchSpace, User, get_async_session
from app.schemas import (
    PodcastCreate,
    PodcastGenerateRequest,
    PodcastRead,
    PodcastUpdate,
)
from app.tasks.podcast_tasks import generate_chat_podcast
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

router = APIRouter()


@router.post("/podcasts/", response_model=PodcastRead)
async def create_podcast(
    podcast: PodcastCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        await check_ownership(session, SearchSpace, podcast.search_space_id, user)
        db_podcast = Podcast(**podcast.model_dump())
        session.add(db_podcast)
        await session.commit()
        await session.refresh(db_podcast)
        return db_podcast
    except HTTPException as he:
        raise he
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Podcast creation failed due to constraint violation",
        ) from None
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error occurred while creating podcast"
        ) from None
    except Exception:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from None


@router.get("/podcasts/", response_model=list[PodcastRead])
async def read_podcasts(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if skip < 0 or limit < 1:
        raise HTTPException(status_code=400, detail="Invalid pagination parameters")
    try:
        result = await session.execute(
            select(Podcast)
            .join(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
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
    try:
        result = await session.execute(
            select(Podcast)
            .join(SearchSpace)
            .filter(Podcast.id == podcast_id, SearchSpace.user_id == user.id)
        )
        podcast = result.scalars().first()
        if not podcast:
            raise HTTPException(
                status_code=404,
                detail="Podcast not found or you don't have permission to access it",
            )
        return podcast
    except HTTPException as he:
        raise he
    except SQLAlchemyError:
        raise HTTPException(
            status_code=500, detail="Database error occurred while fetching podcast"
        ) from None


@router.put("/podcasts/{podcast_id}", response_model=PodcastRead)
async def update_podcast(
    podcast_id: int,
    podcast_update: PodcastUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        db_podcast = await read_podcast(podcast_id, session, user)
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
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Database error occurred while updating podcast"
        ) from None


@router.delete("/podcasts/{podcast_id}", response_model=dict)
async def delete_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        db_podcast = await read_podcast(podcast_id, session, user)
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


async def generate_chat_podcast_with_new_session(
    chat_id: int, search_space_id: int, podcast_title: str, user_id: int
):
    """Create a new session and process chat podcast generation."""
    from app.db import async_session_maker

    async with async_session_maker() as session:
        try:
            await generate_chat_podcast(
                session, chat_id, search_space_id, podcast_title, user_id
            )
        except Exception as e:
            import logging

            logging.error(f"Error generating podcast from chat: {e!s}")


@router.post("/podcasts/generate/")
async def generate_podcast(
    request: PodcastGenerateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        # Check if the user owns the search space
        await check_ownership(session, SearchSpace, request.search_space_id, user)

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
                    chat_id, request.search_space_id, request.podcast_title, user.id
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
    """Stream a podcast audio file."""
    try:
        # Get the podcast and check if user has access
        result = await session.execute(
            select(Podcast)
            .join(SearchSpace)
            .filter(Podcast.id == podcast_id, SearchSpace.user_id == user.id)
        )
        podcast = result.scalars().first()

        if not podcast:
            raise HTTPException(
                status_code=404,
                detail="Podcast not found or you don't have permission to access it",
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
    try:
        # Get the podcast and check if user has access
        result = await session.execute(
            select(Podcast)
            .join(SearchSpace)
            .filter(Podcast.chat_id == chat_id, SearchSpace.user_id == user.id)
        )
        podcast = result.scalars().first()

        return podcast
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching podcast: {e!s}"
        ) from e
