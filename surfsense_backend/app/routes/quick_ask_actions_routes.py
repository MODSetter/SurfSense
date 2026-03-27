from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import QuickAskAction, User, get_async_session
from app.schemas.quick_ask_actions import (
    QuickAskActionCreate,
    QuickAskActionRead,
    QuickAskActionUpdate,
)
from app.users import current_active_user

router = APIRouter(tags=["Quick Ask Actions"])


@router.get("/quick-ask-actions", response_model=list[QuickAskActionRead])
async def list_actions(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    query = select(QuickAskAction).where(QuickAskAction.user_id == user.id)
    if search_space_id is not None:
        query = query.where(QuickAskAction.search_space_id == search_space_id)
    query = query.order_by(QuickAskAction.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.post("/quick-ask-actions", response_model=QuickAskActionRead)
async def create_action(
    body: QuickAskActionCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    action = QuickAskAction(
        user_id=user.id,
        search_space_id=body.search_space_id,
        name=body.name,
        prompt=body.prompt,
        mode=body.mode,
        icon=body.icon,
    )
    session.add(action)
    await session.commit()
    await session.refresh(action)
    return action


@router.put("/quick-ask-actions/{action_id}", response_model=QuickAskActionRead)
async def update_action(
    action_id: int,
    body: QuickAskActionUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(QuickAskAction).where(
            QuickAskAction.id == action_id,
            QuickAskAction.user_id == user.id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(action, field, value)

    session.add(action)
    await session.commit()
    await session.refresh(action)
    return action


@router.delete("/quick-ask-actions/{action_id}")
async def delete_action(
    action_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    result = await session.execute(
        select(QuickAskAction).where(
            QuickAskAction.id == action_id,
            QuickAskAction.user_id == user.id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")

    await session.delete(action)
    await session.commit()
    return {"success": True}
