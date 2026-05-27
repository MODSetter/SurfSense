"""``RunService`` — dispatch and history of automation runs."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import DispatchError
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.triggers.manual import dispatch_manual_run
from app.db import Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission


class RunService:
    """Lifecycle of the ``AutomationRun`` resource."""

    def __init__(self, *, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def dispatch_manual(
        self,
        *,
        automation_id: int,
        runtime_inputs: dict[str, Any] | None,
    ) -> AutomationRun:
        """Fire a manual run via the registered manual trigger."""
        await self._authorize(automation_id, Permission.AUTOMATIONS_EXECUTE.value)
        try:
            return await dispatch_manual_run(
                session=self.session,
                automation_id=automation_id,
                runtime_inputs=runtime_inputs,
            )
        except DispatchError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def list(
        self,
        *,
        automation_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[AutomationRun], int]:
        """Return a page of runs for an automation, newest first."""
        await self._authorize(automation_id, Permission.AUTOMATIONS_READ.value)

        base = select(AutomationRun).where(AutomationRun.automation_id == automation_id)
        total = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )

        rows = (
            await self.session.execute(
                base.order_by(AutomationRun.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

    async def get(self, *, automation_id: int, run_id: int) -> AutomationRun:
        await self._authorize(automation_id, Permission.AUTOMATIONS_READ.value)
        run = await self.session.get(AutomationRun, run_id)
        if run is None or run.automation_id != automation_id:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")
        return run

    async def _authorize(self, automation_id: int, permission: str) -> Automation:
        automation = await self.session.get(Automation, automation_id)
        if automation is None:
            raise HTTPException(
                status_code=404, detail=f"automation {automation_id} not found"
            )
        await check_permission(
            self.session,
            self.user,
            automation.search_space_id,
            permission,
            f"You don't have permission to {permission.split(':')[1]} automations in this search space",
        )
        return automation


def get_run_service(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> RunService:
    return RunService(session=session, user=user)
