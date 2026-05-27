"""Routes for the ``Automation`` resource."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends

from app.automations.services import AutomationService, get_automation_service

router = APIRouter()


@router.post("/automations/{automation_id}/run")
async def run_automation_now(
    automation_id: int,
    payload: dict[str, Any] | None = Body(default=None),
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    """Fire a manual run."""
    run = await service.run_now(automation_id=automation_id, payload=payload)
    return {"run_id": run.id, "status": run.status.value}
