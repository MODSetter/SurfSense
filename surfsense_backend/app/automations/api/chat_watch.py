"""HTTP routes for chat watches (automations bound to a chat thread).

A watch is an automation whose plan re-posts a question into a chat on a
schedule. These routes let the chat UI show watch state and controls:

* ``GET /automations/watches`` — the watches bound to a thread (is-watched + list).
* ``POST /automations/{automation_id}/run`` — run a watch now (manual refresh).

Stopping a watch is a plain ``DELETE /automations/{automation_id}``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from app.automations.schemas.api import AutomationList, AutomationSummary, RunSummary
from app.automations.services import AutomationService, get_automation_service
from app.automations.services.chat_watch import find_watches_for_thread, run_watch_now

router = APIRouter()


@router.get("/automations/watches", response_model=AutomationList)
async def list_watches(
    workspace_id: int = Query(...),
    thread_id: int = Query(...),
    service: AutomationService = Depends(get_automation_service),
) -> AutomationList:
    """List the watches bound to a chat thread (empty when it isn't watched)."""
    watches = await find_watches_for_thread(
        service, workspace_id=workspace_id, thread_id=thread_id
    )
    return AutomationList(
        items=[AutomationSummary.model_validate(a) for a in watches],
        total=len(watches),
    )


@router.post(
    "/automations/{automation_id}/run",
    response_model=RunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_watch(
    automation_id: int,
    service: AutomationService = Depends(get_automation_service),
) -> RunSummary:
    """Enqueue an immediate run of a watch (manual refresh)."""
    run = await run_watch_now(service, automation_id=automation_id)
    return RunSummary.model_validate(run)
