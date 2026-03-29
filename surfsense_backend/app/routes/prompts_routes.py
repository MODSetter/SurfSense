from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Prompt, User, get_async_session
from app.schemas.prompts import (
    PromptCreate,
    PromptRead,
    PromptUpdate,
)
from app.users import current_active_user

router = APIRouter(tags=["Prompts"])


@router.get("/prompts", response_model=list[PromptRead])
async def list_prompts(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    query = select(Prompt).where(Prompt.user_id == user.id)
    if search_space_id is not None:
        query = query.where(Prompt.search_space_id == search_space_id)
    query = query.order_by(Prompt.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.post("/prompts", response_model=PromptRead)
async def create_prompt(
    body: PromptCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    prompt = Prompt(
        user_id=user.id,
        search_space_id=body.search_space_id,
        name=body.name,
        prompt=body.prompt,
        mode=body.mode,
        icon=body.icon,
    )
    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return prompt


@router.put("/prompts/{prompt_id}", response_model=PromptRead)
async def update_prompt(
    prompt_id: int,
    body: PromptUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Prompt).where(
            Prompt.id == prompt_id,
            Prompt.user_id == user.id,
        )
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(prompt, field, value)

    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return prompt


@router.delete("/prompts/{prompt_id}")
async def delete_prompt(
    prompt_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Prompt).where(
            Prompt.id == prompt_id,
            Prompt.user_id == user.id,
        )
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    await session.delete(prompt)
    await session.commit()
    return {"success": True}
