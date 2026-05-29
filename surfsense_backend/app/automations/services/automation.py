"""``AutomationService`` — orchestration for the ``Automation`` resource."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.api import (
    AutomationCreate,
    AutomationUpdate,
    TriggerCreate,
)
from app.automations.schemas.definition.envelope import AutomationModels
from app.automations.services.model_policy import (
    AutomationModelPolicyError,
    assert_automation_models_billable,
    get_automation_model_eligibility,
)
from app.automations.triggers import get_trigger
from app.automations.triggers.schedule import compute_next_fire_at
from app.db import Permission, SearchSpace, User, get_async_session
from app.users import current_active_user
from app.utils.rbac import check_permission


class AutomationService:
    """Lifecycle of the ``Automation`` resource."""

    def __init__(self, *, session: AsyncSession, user: User) -> None:
        self.session = session
        self.user = user

    async def create(self, payload: AutomationCreate) -> Automation:
        """Create an automation and its initial triggers in one transaction."""
        await self._authorize(
            payload.search_space_id, Permission.AUTOMATIONS_CREATE.value
        )
        search_space = await self._assert_models_billable(payload.search_space_id)

        # Snapshot the search space's current (already-validated) model prefs onto
        # the definition so runs are insulated from later chat/search-space model
        # changes. Captured ids are guaranteed billable by the check above.
        payload.definition.models = AutomationModels(
            agent_llm_id=search_space.agent_llm_id or 0,
            image_generation_config_id=search_space.image_generation_config_id or 0,
            vision_llm_config_id=search_space.vision_llm_config_id or 0,
        )

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
            (
                await self.session.execute(
                    base.order_by(Automation.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total or 0)

    async def get(self, automation_id: int) -> Automation:
        """Get an automation with its triggers loaded."""
        automation = await self._get_with_triggers_or_raise(automation_id)
        await self._authorize(
            automation.search_space_id, Permission.AUTOMATIONS_READ.value
        )
        return automation

    async def update(self, automation_id: int, patch: AutomationUpdate) -> Automation:
        """Patch fields. Bumps ``version`` when ``definition`` changes."""
        automation = await self._get_with_triggers_or_raise(automation_id)
        await self._authorize(
            automation.search_space_id, Permission.AUTOMATIONS_UPDATE.value
        )

        data = patch.model_dump(exclude_unset=True)

        if "name" in data:
            automation.name = data["name"]
        if "description" in data:
            automation.description = data["description"]
        if "status" in data:
            automation.status = data["status"]
        if "definition" in data:
            new_def = patch.definition.model_dump(mode="json", by_alias=True)
            # Preserve the captured model snapshot across edits so a definition
            # change never silently re-binds the automation to the current chat
            # model selection. Backend-managed; survives whether or not the
            # client round-trips ``models``.
            existing_models = (automation.definition or {}).get("models")
            if existing_models is not None:
                new_def["models"] = existing_models
            automation.definition = new_def
            automation.version += 1

        await self.session.commit()
        return await self._get_with_triggers_or_raise(automation_id)

    async def delete(self, automation_id: int) -> None:
        """Delete an automation; FK cascades remove triggers and runs."""
        automation = await self._get_or_raise(automation_id)
        await self._authorize(
            automation.search_space_id, Permission.AUTOMATIONS_DELETE.value
        )
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

    async def model_eligibility(self, *, search_space_id: int) -> dict:
        """Return whether a search space's models are billable for automations.

        ``{"allowed": bool, "violations": [{kind, config_id, reason}, ...]}``.
        """
        await self._authorize(search_space_id, Permission.AUTOMATIONS_READ.value)
        search_space = await self.session.get(SearchSpace, search_space_id)
        if search_space is None:
            raise HTTPException(
                status_code=404, detail=f"search space {search_space_id} not found"
            )
        return get_automation_model_eligibility(search_space)

    async def _assert_models_billable(self, search_space_id: int) -> SearchSpace:
        """Reject creation when the search space's models aren't billable.

        Automations may only use premium global models or user BYOK models; free
        global models and Auto mode are blocked. Mirrors the runtime backstop in
        ``agent_task`` so users can't save an automation that would fail to run.

        Returns the loaded :class:`SearchSpace` so the caller can capture its
        model prefs without a second DB read.
        """
        search_space = await self.session.get(SearchSpace, search_space_id)
        if search_space is None:
            raise HTTPException(
                status_code=404, detail=f"search space {search_space_id} not found"
            )
        try:
            assert_automation_models_billable(search_space)
        except AutomationModelPolicyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return search_space

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
        raise HTTPException(
            status_code=422, detail=f"unknown trigger type {spec.type.value!r}"
        )

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
