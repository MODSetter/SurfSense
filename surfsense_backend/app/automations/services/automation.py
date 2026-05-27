"""``AutomationService`` — orchestration for the ``Automation`` resource."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.dispatch import DispatchError
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.triggers.manual import dispatch_manual_run
from app.db import Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission


class AutomationService:
    """Service for the ``Automation`` resource."""

    def __init__(self, *, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def run_now(
        self,
        *,
        automation_id: int,
        payload: dict[str, Any] | None,
    ) -> AutomationRun:
        """Fire a manual run for ``automation_id``."""
        automation = await self._get_automation_or_raise(automation_id)
        await check_permission(
            self.session,
            self.user,
            automation.search_space_id,
            Permission.AUTOMATIONS_EXECUTE.value,
            "You don't have permission to execute automations in this search space",
        )

        try:
            return await dispatch_manual_run(
                session=self.session,
                automation_id=automation_id,
                payload=payload,
            )
        except DispatchError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def _get_automation_or_raise(self, automation_id: int) -> Automation:
        """Get the automation by id; 404 if missing."""
        automation = await self.session.get(Automation, automation_id)
        if automation is None:
            raise HTTPException(
                status_code=404, detail=f"automation {automation_id} not found"
            )
        return automation


def get_automation_service(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> AutomationService:
    return AutomationService(session=session, user=user)
