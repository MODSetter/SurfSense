"""Routes for search-space team memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import User, get_async_session
from app.services.memory import (
    MemoryRead,
    MemoryScope,
    memory_limits,
    read_memory,
    reset_memory,
    save_memory,
)
from app.users import get_auth_context
from app.utils.rbac import check_search_space_access

router = APIRouter()


class TeamMemoryUpdate(BaseModel):
    memory_md: str


@router.get("/searchspaces/{search_space_id}/memory", response_model=MemoryRead)
async def get_team_memory(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    await check_search_space_access(session, auth, search_space_id)
    memory_md = await read_memory(
        scope=MemoryScope.TEAM,
        target_id=search_space_id,
        session=session,
    )
    return MemoryRead(memory_md=memory_md, limits=memory_limits())


@router.put("/searchspaces/{search_space_id}/memory", response_model=MemoryRead)
async def update_team_memory(
    search_space_id: int,
    body: TeamMemoryUpdate,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    await check_search_space_access(session, auth, search_space_id)
    result = await save_memory(
        scope=MemoryScope.TEAM,
        target_id=search_space_id,
        content=body.memory_md,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return MemoryRead(memory_md=result.memory_md, limits=memory_limits())


@router.post("/searchspaces/{search_space_id}/memory/reset", response_model=MemoryRead)
async def reset_team_memory(
    search_space_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
):
    user = auth.user
    await check_search_space_access(session, auth, search_space_id)
    result = await reset_memory(
        scope=MemoryScope.TEAM,
        target_id=search_space_id,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return MemoryRead(memory_md=result.memory_md, limits=memory_limits())
