"""HTTP routes for triggers attached to an automation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.automations.schemas.api import TriggerCreate, TriggerDetail, TriggerUpdate
from app.automations.services import TriggerService, get_trigger_service

router = APIRouter()


@router.post(
    "/automations/{automation_id}/triggers",
    response_model=TriggerDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_trigger(
    automation_id: int,
    payload: TriggerCreate,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerDetail:
    """Attach a new trigger to an automation."""
    trigger = await service.add(automation_id=automation_id, payload=payload)
    return TriggerDetail.model_validate(trigger)


@router.patch(
    "/automations/{automation_id}/triggers/{trigger_id}",
    response_model=TriggerDetail,
)
async def update_trigger(
    automation_id: int,
    trigger_id: int,
    patch: TriggerUpdate,
    service: TriggerService = Depends(get_trigger_service),
) -> TriggerDetail:
    """Toggle ``enabled`` or replace ``params``. Trigger type is immutable."""
    trigger = await service.update(
        automation_id=automation_id, trigger_id=trigger_id, patch=patch
    )
    return TriggerDetail.model_validate(trigger)


@router.delete(
    "/automations/{automation_id}/triggers/{trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_trigger(
    automation_id: int,
    trigger_id: int,
    service: TriggerService = Depends(get_trigger_service),
) -> None:
    """Detach a trigger from an automation."""
    await service.remove(automation_id=automation_id, trigger_id=trigger_id)
