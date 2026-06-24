"""``AutomationService`` — orchestration for the ``Automation`` resource."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.context import AuthContext
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
    assert_models_billable,
    get_automation_model_eligibility,
)
from app.automations.triggers import get_trigger
from app.automations.triggers.builtin.schedule import compute_next_fire_at
from app.db import Permission, SearchSpace, get_async_session
from app.users import get_auth_context
from app.utils.rbac import check_permission


class AutomationService:
    """Lifecycle of the ``Automation`` resource."""

    def __init__(self, *, session: AsyncSession, auth: AuthContext) -> None:
        self.session = session
        self.auth = auth
        self.user = auth.user

    async def create(self, payload: AutomationCreate) -> Automation:
        """Create an automation and its initial triggers in one transaction."""
        await self._authorize(
            payload.search_space_id, Permission.AUTOMATIONS_CREATE.value
        )

        # Capture the model profile onto the definition so runs are insulated
        # from later chat/search-space model changes. Two sources:
        #   1. Explicit per-automation selection in ``payload.definition.models``
        #      (manual builder + chat approval card). Validate the chosen ids.
        #   2. Fallback (no selection): snapshot the search space's current prefs.
        # Either way the captured ids are guaranteed billable (premium/BYOK).
        selected_models = payload.definition.models
        if selected_models is not None:
            self._assert_selected_models_billable(selected_models)
        else:
            search_space = await self._assert_models_billable(payload.search_space_id)
            payload.definition.models = AutomationModels(
                chat_model_id=search_space.chat_model_id or 0,
                image_gen_model_id=search_space.image_gen_model_id or 0,
                vision_model_id=search_space.vision_model_id or 0,
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
            # Model snapshot handling on edit:
            #   * absent in the patch  -> preserve the captured snapshot
            #     (a non-model definition change never silently re-binds the
            #     automation to the current chat/search-space selection).
            #   * unchanged from the snapshot -> keep as-is, no re-validation
            #     (so editing an automation whose captured model later drifted
            #     out of premium isn't blocked by an unrelated name/schedule edit).
            #   * genuinely changed -> validate the new selection (422 on a
            #     non-billable pick), then accept it.
            existing_models = (automation.definition or {}).get("models")
            provided_models = new_def.get("models")
            if provided_models is None:
                if existing_models is not None:
                    new_def["models"] = existing_models
            elif provided_models != existing_models:
                self._assert_selected_models_billable(patch.definition.models)
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

    def _assert_selected_models_billable(self, models: AutomationModels) -> None:
        """Reject creation when an explicitly selected model isn't billable.

        Used when the client supplies ``definition.models`` (per-automation
        selection from the builder or chat approval card). Same policy as the
        search-space path: premium global or BYOK only, no free/Auto.
        """
        try:
            assert_models_billable(
                chat_model_id=models.chat_model_id,
                image_gen_model_id=models.image_gen_model_id,
                vision_model_id=models.vision_model_id,
            )
        except AutomationModelPolicyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    async def _authorize(self, search_space_id: int, permission: str) -> None:
        await check_permission(
            self.session,
            self.auth,
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
    auth: AuthContext = Depends(get_auth_context),
) -> AutomationService:
    return AutomationService(session=session, auth=auth)
