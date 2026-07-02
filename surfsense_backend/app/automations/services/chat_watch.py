"""A chat watch is an automation bound to a chat: a ``schedule`` trigger firing
a single ``chat_message`` step that re-posts the question into the same thread.

Starting a watch creates that automation; stopping deletes it. Whether a chat
is watched is derived from the plan (``plan_targets_thread``), not a stored flag.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.run import AutomationRun
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.schemas.api import AutomationCreate, TriggerCreate
from app.automations.schemas.definition import AutomationDefinition, PlanStep
from app.automations.services.automation import AutomationService

WATCH_ACTION_TYPE = "chat_message"
_WATCH_STEP_ID = "watch"
_NAME_MAX = 200
# Watches per chat are few; one generous page finds them all.
_WATCH_SCAN_LIMIT = 500


def _derive_name(message: str) -> str:
    """A short, human name for the watch from the question it re-asks."""
    condensed = " ".join(message.split())
    label = condensed[:80].rstrip()
    return f"Watch: {label}" if label else "Watch"


def _build_watch_payload(
    *,
    workspace_id: int,
    thread_id: int,
    message: str,
    cron: str,
    timezone: str,
    name: str | None,
    description: str | None,
) -> AutomationCreate:
    watch_name = (name or _derive_name(message))[:_NAME_MAX]
    return AutomationCreate(
        workspace_id=workspace_id,
        name=watch_name,
        description=description,
        definition=AutomationDefinition(
            name=watch_name,
            plan=[
                PlanStep(
                    step_id=_WATCH_STEP_ID,
                    action=WATCH_ACTION_TYPE,
                    params={"thread_id": thread_id, "message": message},
                )
            ],
        ),
        triggers=[
            TriggerCreate(
                type=TriggerType.SCHEDULE,
                params={"cron": cron, "timezone": timezone},
                enabled=True,
            )
        ],
    )


async def create_watch(
    service: AutomationService,
    *,
    workspace_id: int,
    thread_id: int,
    message: str,
    cron: str,
    timezone: str,
    name: str | None = None,
    description: str | None = None,
) -> Automation:
    """Bind a schedule + chat_message watch automation to ``thread_id``."""
    payload = _build_watch_payload(
        workspace_id=workspace_id,
        thread_id=thread_id,
        message=message,
        cron=cron,
        timezone=timezone,
        name=name,
        description=description,
    )
    return await service.create(payload)


async def stop_watch(service: AutomationService, *, automation_id: int) -> None:
    """Stop a watch by deleting its automation; the chat reverts to normal."""
    await service.delete(automation_id)


def plan_targets_thread(definition: dict[str, Any] | None, thread_id: int) -> bool:
    """Whether an automation's plan re-posts into ``thread_id`` (i.e. is a watch).

    Pure predicate over the persisted ``definition`` JSON so callers can filter
    a workspace's automations without a DB round-trip per row.
    """
    for step in (definition or {}).get("plan", []):
        if step.get("action") != WATCH_ACTION_TYPE:
            continue
        if (step.get("params") or {}).get("thread_id") == thread_id:
            return True
    return False


async def find_watches_for_thread(
    service: AutomationService,
    *,
    workspace_id: int,
    thread_id: int,
) -> list[Automation]:
    """Return the workspace automations that watch ``thread_id`` (i.e. its watches)."""
    automations, _total = await service.list(
        workspace_id=workspace_id, limit=_WATCH_SCAN_LIMIT, offset=0
    )
    return [a for a in automations if plan_targets_thread(a.definition, thread_id)]


def schedule_trigger(automation: Automation) -> AutomationTrigger | None:
    """The automation's ``schedule`` trigger row, or ``None``."""
    for trigger in automation.triggers:
        if trigger.type == TriggerType.SCHEDULE:
            return trigger
    return None


async def run_watch_now(
    service: AutomationService,
    *,
    automation_id: int,
) -> AutomationRun:
    """Enqueue an immediate run of a watch (a manual refresh)."""
    # Lazy: launch_run pulls in the automation task graph, which imports
    # multi_agent_chat; this module is imported from there, so a top-level
    # import would cycle.
    from app.automations.dispatch import launch as launch_mod

    automation = await service.get(automation_id)
    trigger = schedule_trigger(automation)
    if trigger is None:
        raise HTTPException(
            status_code=422, detail="watch has no schedule trigger to run"
        )
    return await launch_mod.launch_run(session=service.session, trigger=trigger)
