from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.db import get_async_session, User, SearchSpace
from app.schemas import SearchSpaceCreate, SearchSpaceUpdate, SearchSpaceRead
from app.users import current_active_user
from app.utils.check_ownership import check_ownership
from fastapi import HTTPException

router = APIRouter()

@router.post("/searchspaces/", response_model=SearchSpaceRead)
async def create_search_space(
    search_space: SearchSpaceCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        db_search_space = SearchSpace(**search_space.model_dump(), user_id=user.id)
        session.add(db_search_space)
        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create search space: {str(e)}"
        )

@router.get("/searchspaces/", response_model=List[SearchSpaceRead])
async def read_search_spaces(
    skip: int = 0,
    limit: int = 200,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        result = await session.execute(
            select(SearchSpace)
            .filter(SearchSpace.user_id == user.id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch search spaces: {str(e)}"
        )

@router.get("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def read_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        search_space = await check_ownership(session, SearchSpace, search_space_id, user)
        return search_space
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch search space: {str(e)}"
        )

@router.put("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def update_search_space(
    search_space_id: int,
    search_space_update: SearchSpaceUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        db_search_space = await check_ownership(session, SearchSpace, search_space_id, user)
        update_data = search_space_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_search_space, key, value)
        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update search space: {str(e)}"
        )

@router.delete("/searchspaces/{search_space_id}", response_model=dict)
async def delete_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    try:
        db_search_space = await check_ownership(session, SearchSpace, search_space_id, user)
        await session.delete(db_search_space)
        await session.commit()
        return {"message": "Search space deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete search space: {str(e)}"
        ) 