"""Integration tests for the chat watch service against real Postgres.

A watch is an automation bound to a chat. These exercise the real
``AutomationService`` (RBAC, the automation model-billing gate, and the
definition JSON round-trip) rather than a fake, so the behaviors the unit
layer can't see are proven end to end:

* creating a watch persists a ``schedule`` + ``chat_message`` automation and
  it reads back as the thread's watch;
* the billing gate rejects a watch when the workspace's models aren't
  billable (Auto/free) — the exact failure a fake service would hide;
* finding watches is thread-scoped; stopping one deletes it;
* run-now refuses an automation that has no schedule trigger.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.automations.persistence.enums.trigger_type import TriggerType
from app.automations.persistence.models.automation import Automation
from app.automations.persistence.models.trigger import AutomationTrigger
from app.automations.services.automation import AutomationService
from app.automations.services.chat_watch import (
    create_watch,
    find_watches_for_thread,
    run_watch_now,
    stop_watch,
)
from app.db import ChatVisibility, NewChatThread, User, Workspace

pytestmark = pytest.mark.integration

_CRON = "0 9 * * 1-5"
_TZ = "UTC"


def _billable(workspace: Workspace) -> None:
    """Give the workspace BYOK (positive id) models so automations are billable."""
    workspace.chat_model_id = 1
    workspace.image_gen_model_id = 1
    workspace.vision_model_id = 1


@pytest_asyncio.fixture
async def service(db_session: AsyncSession, db_user: User) -> AutomationService:
    return AutomationService(session=db_session, auth=AuthContext.session(db_user))


@pytest_asyncio.fixture
async def thread(
    db_session: AsyncSession, db_user: User, db_workspace: Workspace
) -> NewChatThread:
    row = NewChatThread(
        title="Watched chat",
        workspace_id=db_workspace.id,
        created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def test_create_watch_persists_and_reads_back_as_the_threads_watch(
    service: AutomationService,
    db_session: AsyncSession,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()
    thread_id = thread.id

    created = await create_watch(
        service,
        workspace_id=db_workspace.id,
        thread_id=thread_id,
        message="what changed on the pricing page?",
        cron=_CRON,
        timezone=_TZ,
    )

    assert created.id is not None
    plan = created.definition["plan"]
    assert len(plan) == 1
    assert plan[0]["action"] == "chat_message"
    assert plan[0]["params"] == {
        "thread_id": thread_id,
        "message": "what changed on the pricing page?",
    }
    schedule = [t for t in created.triggers if t.type == TriggerType.SCHEDULE]
    assert len(schedule) == 1
    assert schedule[0].params["cron"] == _CRON

    found = await find_watches_for_thread(
        service, workspace_id=db_workspace.id, thread_id=thread_id
    )
    assert [a.id for a in found] == [created.id]


async def test_create_watch_rejected_when_workspace_models_not_billable(
    service: AutomationService,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    # Default workspace has no model prefs (Auto/None) -> not billable.
    with pytest.raises(HTTPException) as exc:
        await create_watch(
            service,
            workspace_id=db_workspace.id,
            thread_id=thread.id,
            message="track it",
            cron=_CRON,
            timezone=_TZ,
        )
    assert exc.value.status_code == 422


async def test_find_watches_is_scoped_to_the_thread(
    service: AutomationService,
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
) -> None:
    _billable(db_workspace)
    await db_session.flush()

    thread_a = NewChatThread(
        title="A", workspace_id=db_workspace.id, created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    thread_b = NewChatThread(
        title="B", workspace_id=db_workspace.id, created_by_id=db_user.id,
        visibility=ChatVisibility.PRIVATE,
    )
    db_session.add_all([thread_a, thread_b])
    await db_session.flush()

    watch_a = await create_watch(
        service, workspace_id=db_workspace.id, thread_id=thread_a.id,
        message="a", cron=_CRON, timezone=_TZ,
    )
    await create_watch(
        service, workspace_id=db_workspace.id, thread_id=thread_b.id,
        message="b", cron=_CRON, timezone=_TZ,
    )

    found = await find_watches_for_thread(
        service, workspace_id=db_workspace.id, thread_id=thread_a.id
    )
    assert [a.id for a in found] == [watch_a.id]


async def test_stop_watch_deletes_and_leaves_the_thread_unwatched(
    service: AutomationService,
    db_session: AsyncSession,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()
    thread_id = thread.id

    created = await create_watch(
        service, workspace_id=db_workspace.id, thread_id=thread_id,
        message="m", cron=_CRON, timezone=_TZ,
    )

    await stop_watch(service, automation_id=created.id)

    found = await find_watches_for_thread(
        service, workspace_id=db_workspace.id, thread_id=thread_id
    )
    assert found == []
    with pytest.raises(HTTPException) as exc:
        await service.get(created.id)
    assert exc.value.status_code == 404


async def test_run_watch_now_rejects_automation_without_schedule_trigger(
    service: AutomationService,
    db_session: AsyncSession,
    db_workspace: Workspace,
    db_user: User,
    thread: NewChatThread,
) -> None:
    # Seed a watch-shaped automation whose only trigger is non-schedule.
    automation = Automation(
        workspace_id=db_workspace.id,
        created_by_user_id=db_user.id,
        name="Watch: broken",
        definition={
            "name": "Watch: broken",
            "plan": [
                {
                    "step_id": "watch",
                    "action": "chat_message",
                    "params": {"thread_id": thread.id, "message": "m"},
                }
            ],
        },
        version=1,
    )
    automation.triggers.append(
        AutomationTrigger(type=TriggerType.EVENT, params={}, enabled=True)
    )
    db_session.add(automation)
    await db_session.flush()

    with pytest.raises(HTTPException) as exc:
        await run_watch_now(service, automation_id=automation.id)
    assert exc.value.status_code == 422
