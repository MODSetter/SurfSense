"""HTTP routes for automation runs (dispatch + history)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status

from app.automations.schemas.api import (
    RunDetail,
    RunDispatched,
    RunList,
    RunSummary,
)
from app.automations.services import RunService, get_run_service

router = APIRouter()


@router.post(
    "/automations/{automation_id}/run",
    response_model=RunDispatched,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_automation_now(
    automation_id: int,
    inputs: dict[str, Any] | None = Body(default=None),
    service: RunService = Depends(get_run_service),
) -> RunDispatched:
    """Fire a manual run.

    ``inputs`` is the runtime payload supplied by the caller; it is merged with
    the manual trigger's ``static_inputs`` (static wins) and validated against
    the automation's input schema.
    """
    run = await service.dispatch_manual(automation_id=automation_id, runtime_inputs=inputs)
    return RunDispatched(run_id=run.id, status=run.status)


@router.get(
    "/automations/{automation_id}/runs",
    response_model=RunList,
)
async def list_runs(
    automation_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: RunService = Depends(get_run_service),
) -> RunList:
    """List run history for an automation, newest first."""
    items, total = await service.list(
        automation_id=automation_id, limit=limit, offset=offset
    )
    return RunList(
        items=[RunSummary.model_validate(r) for r in items],
        total=total,
    )


@router.get(
    "/automations/{automation_id}/runs/{run_id}",
    response_model=RunDetail,
)
async def get_run(
    automation_id: int,
    run_id: int,
    service: RunService = Depends(get_run_service),
) -> RunDetail:
    """Get the full record of a single run, including step results and artifacts."""
    run = await service.get(automation_id=automation_id, run_id=run_id)
    return RunDetail.model_validate(run)
