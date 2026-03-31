from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import Prompt, User, get_async_session
from app.prompts.system_defaults import SYSTEM_PROMPT_DEFAULTS, SYSTEM_PROMPT_SLUGS
from app.schemas.prompts import (
    PromptCreate,
    PromptRead,
    PromptUpdate,
    PublicPromptRead,
    SystemPromptUpdate,
)
from app.users import current_active_user

router = APIRouter(tags=["Prompts"])


def _prompt_to_read(prompt: Prompt) -> PromptRead:
    source = "system" if prompt.system_prompt_slug else "custom"
    return PromptRead(
        id=prompt.id,
        name=prompt.name,
        prompt=prompt.prompt,
        mode=prompt.mode.value if hasattr(prompt.mode, "value") else prompt.mode,
        search_space_id=prompt.search_space_id,
        is_public=prompt.is_public,
        created_at=prompt.created_at,
        source=source,
        system_prompt_slug=prompt.system_prompt_slug,
        is_modified=source == "system",
    )


@router.get("/prompts", response_model=list[PromptRead])
async def list_prompts(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    query = select(Prompt).where(Prompt.user_id == user.id)
    if search_space_id is not None:
        query = query.where(Prompt.search_space_id == search_space_id)
    result = await session.execute(query)
    user_prompts = result.scalars().all()

    overrides = {p.system_prompt_slug: p for p in user_prompts if p.system_prompt_slug}
    custom_prompts = [p for p in user_prompts if not p.system_prompt_slug]

    merged: list[PromptRead] = []
    for default in SYSTEM_PROMPT_DEFAULTS:
        slug = default["slug"]
        override = overrides.get(slug)
        if override:
            merged.append(_prompt_to_read(override))
        else:
            merged.append(
                PromptRead(
                    id=None,
                    name=default["name"],
                    prompt=default["prompt"],
                    mode=default["mode"],
                    source="system",
                    system_prompt_slug=slug,
                    is_modified=False,
                )
            )

    for p in sorted(custom_prompts, key=lambda x: x.created_at, reverse=True):
        merged.append(_prompt_to_read(p))

    return merged


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
    )
    session.add(prompt)
    await session.commit()
    await session.refresh(prompt)
    return _prompt_to_read(prompt)


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
    return _prompt_to_read(prompt)


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


@router.put("/prompts/system/{slug}", response_model=PromptRead)
async def update_system_prompt(
    slug: str,
    body: SystemPromptUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if slug not in SYSTEM_PROMPT_SLUGS:
        raise HTTPException(status_code=404, detail="System prompt not found")

    result = await session.execute(
        select(Prompt).where(
            Prompt.user_id == user.id,
            Prompt.system_prompt_slug == slug,
        )
    )
    override = result.scalar_one_or_none()

    default = next(d for d in SYSTEM_PROMPT_DEFAULTS if d["slug"] == slug)

    if override:
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(override, field, value)
    else:
        updates = body.model_dump(exclude_unset=True)
        override = Prompt(
            user_id=user.id,
            system_prompt_slug=slug,
            name=updates.get("name", default["name"]),
            prompt=updates.get("prompt", default["prompt"]),
            mode=updates.get("mode", default["mode"]),
        )

    session.add(override)
    await session.commit()
    await session.refresh(override)
    return _prompt_to_read(override)


@router.delete("/prompts/system/{slug}")
async def reset_system_prompt(
    slug: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    if slug not in SYSTEM_PROMPT_SLUGS:
        raise HTTPException(status_code=404, detail="System prompt not found")

    result = await session.execute(
        select(Prompt).where(
            Prompt.user_id == user.id,
            Prompt.system_prompt_slug == slug,
        )
    )
    override = result.scalar_one_or_none()
    if not override:
        return {"success": True}

    await session.delete(override)
    await session.commit()
    return {"success": True}


@router.get("/prompts/public", response_model=list[PublicPromptRead])
async def list_public_prompts(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Prompt)
        .options(selectinload(Prompt.user))
        .where(Prompt.is_public.is_(True))
        .order_by(Prompt.created_at.desc())
    )
    prompts = result.scalars().all()
    return [
        PublicPromptRead(
            **_prompt_to_read(p).model_dump(),
            author_name=p.user.email if p.user else None,
        )
        for p in prompts
    ]


@router.post("/prompts/{prompt_id}/copy", response_model=PromptRead)
async def copy_public_prompt(
    prompt_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(Prompt).where(
            Prompt.id == prompt_id,
            Prompt.is_public.is_(True),
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Prompt not found")

    copy = Prompt(
        user_id=user.id,
        name=source.name,
        prompt=source.prompt,
        mode=source.mode,
        is_public=False,
    )
    session.add(copy)
    await session.commit()
    await session.refresh(copy)
    return _prompt_to_read(copy)
