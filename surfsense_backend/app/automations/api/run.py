"""HTTP routes for automation run history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.automations.schemas.api import RunDetail, RunList, RunSummary
from app.automations.services import RunService, get_run_service

router = APIRouter()


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
