"""Routes for user memory management."""

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

router = APIRouter()


class MemoryRead(BaseModel):
    memory_md: str


class MemoryUpdate(BaseModel):
    memory_md: str


@router.get("/users/me/memory", response_model=MemoryRead)
async def get_user_memory(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    memory_md = await read_memory(
        scope=MemoryScope.USER,
        target_id=user.id,
        session=session,
    )
    return MemoryRead(memory_md=memory_md)


@router.put("/users/me/memory", response_model=MemoryRead)
async def update_user_memory(
    body: MemoryUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await save_memory(
        scope=MemoryScope.USER,
        target_id=user.id,
        content=body.memory_md,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return MemoryRead(memory_md=result.memory_md)


@router.post("/users/me/memory/reset", response_model=MemoryRead)
async def reset_user_memory(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    result = await reset_memory(
        scope=MemoryScope.USER,
        target_id=user.id,
        session=session,
    )
    if result.status == "error":
        raise HTTPException(status_code=400, detail=result.message)
    return MemoryRead(memory_md=result.memory_md)
