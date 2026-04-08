"""Routes for user memory management (personal memory.md)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.tools.update_memory import MEMORY_HARD_LIMIT
from app.db import User, get_async_session
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
    await session.refresh(user, ["memory_md"])
    return MemoryRead(memory_md=user.memory_md or "")


@router.put("/users/me/memory", response_model=MemoryRead)
async def update_user_memory(
    body: MemoryUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    if len(body.memory_md) > MEMORY_HARD_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Memory exceeds {MEMORY_HARD_LIMIT:,} character limit ({len(body.memory_md):,} chars).",
        )
    user.memory_md = body.memory_md
    session.add(user)
    await session.commit()
    await session.refresh(user, ["memory_md"])
    return MemoryRead(memory_md=user.memory_md or "")
