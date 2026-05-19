"""Routes for search-space team memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.services.memory import (
    MemoryScope,
    read_memory,
    reset_memory,
    save_memory,
)
from app.users import current_active_user
from app.utils.rbac import check_search_space_access

router = APIRouter()


class TeamMemoryRead(BaseModel):
    memory_md: str


class TeamMemoryUpdate(BaseModel):
    memory_md: str


@router.get("/searchspaces/{search_space_id}/memory", response_model=TeamMemoryRead)
async def get_team_memory(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await check_search_space_access(session, user, search_space_id)
    memory_md = await read_memory(
        scope=MemoryScope.TEAM,
        target_id=search_space_id,
        session=session,
    )
    return TeamMemoryRead(memory_md=memory_md)


@router.put("/searchspaces/{search_space_id}/memory", response_model=TeamMemoryRead)
async def update_team_memory(
    search_space_id: int,
    body: TeamMemoryUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await check_search_space_access(session, user, search_space_id)
    result = await save_memory(
        scope=MemoryScope.TEAM,
        target_id=search_space_id,
        content=body.memory_md,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return TeamMemoryRead(memory_md=result.memory_md)


@router.post("/searchspaces/{search_space_id}/memory/reset", response_model=TeamMemoryRead)
async def reset_team_memory(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    await check_search_space_access(session, user, search_space_id)
    result = await reset_memory(
        scope=MemoryScope.TEAM,
        target_id=search_space_id,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return TeamMemoryRead(memory_md=result.memory_md)
