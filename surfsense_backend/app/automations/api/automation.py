"""Routes for the ``Automation`` resource."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends

from app.automations.api.schemas import RunDispatched
from app.automations.services import AutomationService, get_automation_service

router = APIRouter()


@router.post("/automations/{automation_id}/run", response_model=RunDispatched)
async def run_automation_now(
    automation_id: int,
    payload: dict[str, Any] | None = Body(default=None),
    service: AutomationService = Depends(get_automation_service),
) -> RunDispatched:
    """Fire a manual run."""
    run = await service.run_now(automation_id=automation_id, payload=payload)
    return RunDispatched(run_id=run.id, status=run.status)
