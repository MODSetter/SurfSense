"""HTTP routes for the ``Automation`` resource."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.automations.schemas.api import (
    AutomationCreate,
    AutomationDetail,
    AutomationList,
    AutomationSummary,
    AutomationUpdate,
)
from app.automations.services import AutomationService, get_automation_service

router = APIRouter()


class ModelEligibilityViolation(BaseModel):
    kind: str
    config_id: int | None
    reason: str


class ModelEligibility(BaseModel):
    allowed: bool
    violations: list[ModelEligibilityViolation]


@router.post(
    "/automations",
    response_model=AutomationDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_automation(
    payload: AutomationCreate,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationDetail:
    """Create an automation, optionally with initial triggers (atomic)."""
    automation = await service.create(payload)
    return AutomationDetail.model_validate(automation)


@router.get("/automations", response_model=AutomationList)
async def list_automations(
    workspace_id: int = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: AutomationService = Depends(get_automation_service),
) -> AutomationList:
    """List automations in a workspace."""
    items, total = await service.list(
        workspace_id=workspace_id, limit=limit, offset=offset
    )
    return AutomationList(
        items=[AutomationSummary.model_validate(a) for a in items],
        total=total,
    )


@router.get("/automations/model-eligibility", response_model=ModelEligibility)
async def get_automation_model_eligibility(
    workspace_id: int = Query(...),
    service: AutomationService = Depends(get_automation_service),
) -> ModelEligibility:
    """Report whether a workspace's models are billable for automations.

    Used by the frontend to gate creation: automations may only use premium
    global models or user BYOK models (free models and Auto mode are blocked).

    NOTE: declared before ``/automations/{automation_id}`` so the literal path
    isn't captured by the int-typed ``{automation_id}`` route.
    """
    result = await service.model_eligibility(workspace_id=workspace_id)
    return ModelEligibility.model_validate(result)


@router.get("/automations/{automation_id}", response_model=AutomationDetail)
async def get_automation(
    automation_id: int,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationDetail:
    """Get one automation with its definition and triggers."""
    automation = await service.get(automation_id)
    return AutomationDetail.model_validate(automation)


@router.patch("/automations/{automation_id}", response_model=AutomationDetail)
async def update_automation(
    automation_id: int,
    patch: AutomationUpdate,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationDetail:
    """Partially update an automation. Triggers are managed separately."""
    automation = await service.update(automation_id, patch)
    return AutomationDetail.model_validate(automation)


@router.delete(
    "/automations/{automation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_automation(
    automation_id: int,
    service: AutomationService = Depends(get_automation_service),
) -> None:
    """Delete an automation; triggers and runs are removed by FK cascade."""
    await service.delete(automation_id)
