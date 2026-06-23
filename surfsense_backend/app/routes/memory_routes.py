"""Routes for user memory management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.services.memory import (
    MemoryRead,
    MemoryScope,
    memory_limits,
    read_memory,
    reset_memory,
    save_memory,
)
from app.users import require_session_context

router = APIRouter()


class MemoryUpdate(BaseModel):
    memory_md: str


@router.get("/users/me/memory", response_model=MemoryRead)
async def get_user_memory(
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    user = auth.user
    memory_md = await read_memory(
        scope=MemoryScope.USER,
        target_id=user.id,
        session=session,
    )
    return MemoryRead(memory_md=memory_md, limits=memory_limits())


@router.put("/users/me/memory", response_model=MemoryRead)
async def update_user_memory(
    body: MemoryUpdate,
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    user = auth.user
    result = await save_memory(
        scope=MemoryScope.USER,
        target_id=user.id,
        content=body.memory_md,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return MemoryRead(memory_md=result.memory_md, limits=memory_limits())


@router.post("/users/me/memory/reset", response_model=MemoryRead)
async def reset_user_memory(
    auth: AuthContext = Depends(require_session_context),
    session: AsyncSession = Depends(get_async_session),
):
    user = auth.user
    result = await reset_memory(
        scope=MemoryScope.USER,
        target_id=user.id,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return MemoryRead(memory_md=result.memory_md, limits=memory_limits())
