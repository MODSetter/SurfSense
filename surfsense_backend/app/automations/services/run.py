"""``RunService`` — read-only access to automation run history."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.auth.context import AuthContext
from app.db import Permission, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission


class RunService:
    """Read-only access to ``AutomationRun`` history."""

    def __init__(self, *, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth

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
            (
                await self.session.execute(
                    base.order_by(AutomationRun.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
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
            self.auth,
            automation.search_space_id,
            permission,
            f"You don't have permission to {permission.split(':')[1]} automations in this search space",
        )
        return automation


def get_run_service(
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> RunService:
    return RunService(session=session, auth=auth)
