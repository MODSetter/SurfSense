from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List
from app.db import get_async_session, User, SearchSpace, Podcast
from app.schemas import PodcastCreate, PodcastUpdate, PodcastRead
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

router = APIRouter()

@router.post("/podcasts/", response_model=PodcastRead)
async def create_podcast(
    podcast: PodcastCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Podcast creation failed due to constraint violation")
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred while creating podcast")
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

@router.get("/podcasts/", response_model=List[PodcastRead])
async def read_podcasts(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
        raise HTTPException(status_code=500, detail="Database error occurred while fetching podcasts")

@router.get("/podcasts/{podcast_id}", response_model=PodcastRead)
async def read_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
                detail="Podcast not found or you don't have permission to access it"
            )
        return podcast
    except HTTPException as he:
        raise he
    except SQLAlchemyError:
        raise HTTPException(status_code=500, detail="Database error occurred while fetching podcast")

@router.put("/podcasts/{podcast_id}", response_model=PodcastRead)
async def update_podcast(
    podcast_id: int,
    podcast_update: PodcastUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
        raise HTTPException(status_code=400, detail="Update failed due to constraint violation")
    except SQLAlchemyError:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred while updating podcast")

@router.delete("/podcasts/{podcast_id}", response_model=dict)
async def delete_podcast(
    podcast_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
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
        raise HTTPException(status_code=500, detail="Database error occurred while deleting podcast") 