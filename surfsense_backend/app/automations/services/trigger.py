"""``TriggerService`` — lifecycle of triggers attached to an automation."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.api import TriggerCreate, TriggerUpdate
from app.automations.triggers import get_trigger
from app.automations.triggers.schedule import compute_next_fire_at
from app.db import Permission, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission


class TriggerService:
    """Lifecycle of the ``AutomationTrigger`` sub-resource."""

    def __init__(self, *, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def add(
        self, *, automation_id: int, payload: TriggerCreate
    ) -> AutomationTrigger:
        automation = await self._authorize_automation(
            automation_id, Permission.AUTOMATIONS_UPDATE.value
        )

        validated_params = _validate_params(payload.type, payload.params)
        trigger = AutomationTrigger(
            automation_id=automation.id,
            type=payload.type,
            params=validated_params,
            static_inputs=payload.static_inputs,
            enabled=payload.enabled,
            next_fire_at=_initial_next_fire(
                payload.type, validated_params, payload.enabled
            ),
        )
        self.session.add(trigger)
        await self.session.commit()
        await self.session.refresh(trigger)
        return trigger

    async def update(
        self,
        *,
        automation_id: int,
        trigger_id: int,
        patch: TriggerUpdate,
    ) -> AutomationTrigger:
        await self._authorize_automation(
            automation_id, Permission.AUTOMATIONS_UPDATE.value
        )
        trigger = await self._get_trigger_or_raise(automation_id, trigger_id)

        data = patch.model_dump(exclude_unset=True)

        if "params" in data:
            trigger.params = _validate_params(trigger.type, data["params"])

        if "static_inputs" in data:
            trigger.static_inputs = data["static_inputs"]

        if "enabled" in data:
            trigger.enabled = data["enabled"]

        # Recompute next_fire_at when schedule timing changed or the trigger was
        # toggled back on.
        if trigger.type == TriggerType.SCHEDULE:
            trigger.next_fire_at = _initial_next_fire(
                trigger.type, trigger.params, trigger.enabled
            )

        await self.session.commit()
        await self.session.refresh(trigger)
        return trigger

    async def remove(self, *, automation_id: int, trigger_id: int) -> None:
        await self._authorize_automation(
            automation_id, Permission.AUTOMATIONS_UPDATE.value
        )
        trigger = await self._get_trigger_or_raise(automation_id, trigger_id)
        await self.session.delete(trigger)
        await self.session.commit()

    async def _authorize_automation(
        self, automation_id: int, permission: str
    ) -> Automation:
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

    async def _get_trigger_or_raise(
        self, automation_id: int, trigger_id: int
    ) -> AutomationTrigger:
        trigger = await self.session.get(AutomationTrigger, trigger_id)
        if trigger is None or trigger.automation_id != automation_id:
            raise HTTPException(
                status_code=404, detail=f"trigger {trigger_id} not found"
            )
        return trigger


def _validate_params(trigger_type: TriggerType, raw: dict) -> dict:
    definition = get_trigger(trigger_type.value)
    if definition is None:
        raise HTTPException(
            status_code=422, detail=f"unknown trigger type {trigger_type.value!r}"
        )
    try:
        validated = definition.params_model.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return validated.model_dump(mode="json")


def _initial_next_fire(
    trigger_type: TriggerType, params: dict, enabled: bool
) -> datetime | None:
    if trigger_type != TriggerType.SCHEDULE or not enabled:
        return None
    return compute_next_fire_at(
        params["cron"], params["timezone"], after=datetime.now(UTC)
    )


def get_trigger_service(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> TriggerService:
    return TriggerService(session=session, user=user)
