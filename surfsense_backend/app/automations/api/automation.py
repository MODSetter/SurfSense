"""HTTP routes for the ``Automation`` resource."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.automations.schemas.api import (
    AutomationCreate,
    AutomationDetail,
    AutomationList,
    AutomationSummary,
    AutomationUpdate,
)
from app.automations.services import AutomationService, get_automation_service

router = APIRouter()


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
    search_space_id: int = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: AutomationService = Depends(get_automation_service),
) -> AutomationList:
    """List automations in a search space."""
    items, total = await service.list(
        search_space_id=search_space_id, limit=limit, offset=offset
    )
    return AutomationList(
        items=[AutomationSummary.model_validate(a) for a in items],
        total=total,
    )


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
