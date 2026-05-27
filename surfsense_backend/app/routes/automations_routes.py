"""Routes for automations. v1: manual ``Run now``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import DispatchError
from app.automations.persistence.models.automation import Automation
from app.automations.triggers.manual import dispatch_manual_run
from app.db import Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


@router.post("/automations/{automation_id}/run")
async def run_automation_now(
    automation_id: int,
    payload: dict[str, Any] | None = Body(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Fire an automation manually. Returns the new run id and status."""
    search_space_id = (
        await session.execute(
            select(Automation.search_space_id).where(Automation.id == automation_id)
        )
    ).scalar_one_or_none()
    if search_space_id is None:
        raise HTTPException(
            status_code=404, detail=f"automation {automation_id} not found"
        )

    await check_permission(
        session,
        user,
        search_space_id,
        Permission.AUTOMATIONS_EXECUTE.value,
        "You don't have permission to execute automations in this search space",
    )

    try:
        run = await dispatch_manual_run(
            session=session,
            automation_id=automation_id,
            payload=payload,
        )
    except DispatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"run_id": run.id, "status": run.status.value}
