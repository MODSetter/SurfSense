from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import SearchSpace, User, get_async_session
from app.schemas import SearchSpaceCreate, SearchSpaceRead, SearchSpaceUpdate
from app.users import current_active_user
from app.utils.check_ownership import check_ownership

router = APIRouter()


@router.post("/searchspaces", response_model=SearchSpaceRead)
async def create_search_space(
    search_space: SearchSpaceCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        search_space_data = search_space.model_dump()

        # citations_enabled defaults to True (handled by Pydantic schema)
        # qna_custom_instructions defaults to None/empty (handled by DB)

        db_search_space = SearchSpace(**search_space_data, user_id=user.id)
        session.add(db_search_space)
        await session.commit()
        await session.refresh(db_search_space)
        return db_search_space
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create search space: {e!s}"
        ) from e


@router.get("/searchspaces", response_model=list[SearchSpaceRead])
async def read_search_spaces(
    skip: int = 0,
    limit: int = 200,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
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
            status_code=500, detail=f"Failed to fetch search spaces: {e!s}"
        ) from e


@router.get("/searchspaces/prompts/community")
async def get_community_prompts():
    """
    Get community-curated prompts for SearchSpace System Instructions.
    This endpoint does not require authentication as it serves public prompts.
    """
    try:
        # Get the path to the prompts YAML file
        prompts_file = (
            Path(__file__).parent.parent
            / "prompts"
            / "public_search_space_prompts.yaml"
        )

        if not prompts_file.exists():
            raise HTTPException(
                status_code=404, detail="Community prompts file not found"
            )

        with open(prompts_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return data.get("prompts", [])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load community prompts: {e!s}"
        ) from e


@router.get("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def read_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        search_space = await check_ownership(
            session, SearchSpace, search_space_id, user
        )
        return search_space

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch search space: {e!s}"
        ) from e


@router.put("/searchspaces/{search_space_id}", response_model=SearchSpaceRead)
async def update_search_space(
    search_space_id: int,
    search_space_update: SearchSpaceUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        db_search_space = await check_ownership(
            session, SearchSpace, search_space_id, user
        )
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
            status_code=500, detail=f"Failed to update search space: {e!s}"
        ) from e


@router.delete("/searchspaces/{search_space_id}", response_model=dict)
async def delete_search_space(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        db_search_space = await check_ownership(
            session, SearchSpace, search_space_id, user
        )
        await session.delete(db_search_space)
        await session.commit()
        return {"message": "Search space deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to delete search space: {e!s}"
        ) from e
