"""Integration tests for the watch HTTP routes (real app, DB, auth).

Watches are seeded through the real service and read back through the mounted
endpoints, exercising query validation, auth, and response mapping. Run-now is
asserted without a broker by spying the Celery enqueue while still persisting a
real PENDING run.
"""

from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.automations.persistence.enums.run_status import RunStatus
from app.automations.persistence.models.run import AutomationRun
from app.automations.services.automation import AutomationService
from app.automations.services.chat_watch import create_watch
from app.db import ChatVisibility, NewChatThread, User, Workspace

pytestmark = pytest.mark.integration

BASE = "/api/v1/automations"
_CRON = "0 9 * * 1-5"
_TZ = "UTC"


def _billable(workspace: Workspace) -> None:
    workspace.chat_model_id = 1
    workspace.image_gen_model_id = 1
    workspace.vision_model_id = 1


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


async def _seed_watch(
    db_session: AsyncSession,
    db_user: User,
    *,
    workspace_id: int,
    thread_id: int,
):
    service = AutomationService(session=db_session, auth=AuthContext.session(db_user))
    return await create_watch(
        service,
        workspace_id=workspace_id,
        thread_id=thread_id,
        message="what changed?",
        cron=_CRON,
        timezone=_TZ,
    )


async def test_list_watches_returns_the_threads_watch(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()
    watch = await _seed_watch(
        db_session, db_user, workspace_id=db_workspace.id, thread_id=thread.id
    )

    resp = await client.get(
        f"{BASE}/watches",
        params={"workspace_id": db_workspace.id, "thread_id": thread.id},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == watch.id


async def test_list_watches_empty_when_thread_not_watched(
    client: httpx.AsyncClient,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    resp = await client.get(
        f"{BASE}/watches",
        params={"workspace_id": db_workspace.id, "thread_id": thread.id},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_run_watch_now_enqueues_and_persists_pending_run(
    client: httpx.AsyncClient,
    enqueue_spy: list[dict],
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()
    watch = await _seed_watch(
        db_session, db_user, workspace_id=db_workspace.id, thread_id=thread.id
    )

    resp = await client.post(f"{BASE}/{watch.id}/run")

    assert resp.status_code == 202
    assert len(enqueue_spy) == 1

    runs = (
        (
            await db_session.execute(
                select(AutomationRun).where(AutomationRun.automation_id == watch.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(runs) == 1
    assert runs[0].status == RunStatus.PENDING
