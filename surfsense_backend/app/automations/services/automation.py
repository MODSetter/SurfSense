"""``AutomationService`` — orchestration for the ``Automation`` resource."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.automations.schemas.api import (
    AutomationCreate,
    AutomationUpdate,
    TriggerCreate,
)
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.triggers import get_trigger
from app.automations.triggers.schedule import compute_next_fire_at
from app.db import Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission


class AutomationService:
    """Lifecycle of the ``Automation`` resource."""

    def __init__(self, *, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def create(self, payload: AutomationCreate) -> Automation:
        """Create an automation and its initial triggers in one transaction."""
        await self._authorize(payload.search_space_id, Permission.AUTOMATIONS_CREATE.value)

        automation = Automation(
            search_space_id=payload.search_space_id,
            created_by_user_id=self.user.id,
            name=payload.name,
            description=payload.description,
            definition=payload.definition.model_dump(mode="json", by_alias=True),
            version=1,
        )
        for spec in payload.triggers:
            automation.triggers.append(_build_trigger(spec))

        self.session.add(automation)
        await self.session.commit()
        return await self._get_with_triggers_or_raise(automation.id)

    async def list(
        self,
        *,
        search_space_id: int,
        limit: int,
        offset: int,
    ) -> tuple[list[Automation], int]:
        """Return a page of automations and the total count."""
        await self._authorize(search_space_id, Permission.AUTOMATIONS_READ.value)

        base = select(Automation).where(Automation.search_space_id == search_space_id)
        total = await self.session.scalar(
            select(func.count()).select_from(base.subquery())
        )

        rows = (
            await self.session.execute(
                base.order_by(Automation.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()
        return list(rows), int(total or 0)

    async def get(self, automation_id: int) -> Automation:
        """Get an automation with its triggers loaded."""
        automation = await self._get_with_triggers_or_raise(automation_id)
        await self._authorize(automation.search_space_id, Permission.AUTOMATIONS_READ.value)
        return automation

    async def update(self, automation_id: int, patch: AutomationUpdate) -> Automation:
        """Patch fields. Bumps ``version`` when ``definition`` changes."""
        automation = await self._get_with_triggers_or_raise(automation_id)
        await self._authorize(automation.search_space_id, Permission.AUTOMATIONS_UPDATE.value)

        data = patch.model_dump(exclude_unset=True)

        if "name" in data:
            automation.name = data["name"]
        if "description" in data:
            automation.description = data["description"]
        if "status" in data:
            automation.status = data["status"]
        if "definition" in data:
            automation.definition = patch.definition.model_dump(mode="json", by_alias=True)
            automation.version += 1

        await self.session.commit()
        return await self._get_with_triggers_or_raise(automation_id)

    async def delete(self, automation_id: int) -> None:
        """Delete an automation; FK cascades remove triggers and runs."""
        automation = await self._get_or_raise(automation_id)
        await self._authorize(automation.search_space_id, Permission.AUTOMATIONS_DELETE.value)
        await self.session.delete(automation)
        await self.session.commit()

    async def _get_or_raise(self, automation_id: int) -> Automation:
        automation = await self.session.get(Automation, automation_id)
        if automation is None:
            raise HTTPException(
                status_code=404, detail=f"automation {automation_id} not found"
            )
        return automation

    async def _get_with_triggers_or_raise(self, automation_id: int) -> Automation:
        stmt = (
            select(Automation)
            .where(Automation.id == automation_id)
            .options(selectinload(Automation.triggers))
        )
        automation = (await self.session.execute(stmt)).scalar_one_or_none()
        if automation is None:
            raise HTTPException(
                status_code=404, detail=f"automation {automation_id} not found"
            )
        return automation

    async def _authorize(self, search_space_id: int, permission: str) -> None:
        await check_permission(
            self.session,
            self.user,
            search_space_id,
            permission,
            f"You don't have permission to {permission.split(':')[1]} automations in this search space",
        )


def _build_trigger(spec: TriggerCreate) -> AutomationTrigger:
    """Validate trigger params via its registered Pydantic model and build the ORM row."""
    definition = get_trigger(spec.type.value)
    if definition is None:
        raise HTTPException(status_code=422, detail=f"unknown trigger type {spec.type.value!r}")

    try:
        validated = definition.params_model.model_validate(spec.params)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    params = validated.model_dump(mode="json")

    next_fire_at = None
    if spec.type == TriggerType.SCHEDULE and spec.enabled:
        next_fire_at = compute_next_fire_at(
            params["cron"], params["timezone"], after=datetime.now(UTC)
        )

    return AutomationTrigger(
        type=spec.type,
        params=params,
        static_inputs=spec.static_inputs,
        enabled=spec.enabled,
        next_fire_at=next_fire_at,
    )


def get_automation_service(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> AutomationService:
    return AutomationService(session=session, user=user)
