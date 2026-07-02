"""Integration tests for the watch chat tools against real service + Postgres.

The tools are thin adapters the intelligence agent calls; here they run their
real path — open a session, build ``AutomationService``, and create / find /
delete / enqueue — against real persistence (RBAC + model gate included), with
only the Celery enqueue spied. This is what proves ``start_watch`` actually
binds a watch, ``stop_watch`` removes it, and ``refresh_watch`` enqueues a run.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools.refresh_watch import (
    create_refresh_watch_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools.start_watch import (
    create_start_watch_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools.stop_watch import (
    create_stop_watch_tool,
)
from app.auth.context import AuthContext
from app.automations.services.automation import AutomationService
from app.automations.services.chat_watch import find_watches_for_thread
from app.db import ChatVisibility, NewChatThread, User, Workspace

pytestmark = pytest.mark.integration

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


async def test_start_watch_tool_binds_a_watch_to_the_chat(
    tools_use_test_session,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()

    tool = create_start_watch_tool(
        workspace_id=db_workspace.id,
        thread_id=thread.id,
        auth_context=AuthContext.session(db_user),
    )
    out = await tool.ainvoke(
        {"message": "what changed?", "cron": _CRON, "timezone": _TZ}
    )

    assert out["status"] == "watching"
    assert isinstance(out["automation_id"], int)

    service = AutomationService(session=db_session, auth=AuthContext.session(db_user))
    found = await find_watches_for_thread(
        service, workspace_id=db_workspace.id, thread_id=thread.id
    )
    assert [a.id for a in found] == [out["automation_id"]]


async def test_start_watch_tool_reports_error_when_models_not_billable(
    tools_use_test_session,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    # Default workspace models are Auto/None -> the automation gate rejects it.
    tool = create_start_watch_tool(
        workspace_id=db_workspace.id,
        thread_id=thread.id,
        auth_context=AuthContext.session(db_user),
    )
    out = await tool.ainvoke(
        {"message": "track it", "cron": _CRON, "timezone": _TZ}
    )
    assert out["status"] == "error"


async def test_stop_watch_tool_removes_the_chats_watch(
    tools_use_test_session,
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()
    auth = AuthContext.session(db_user)

    start = create_start_watch_tool(
        workspace_id=db_workspace.id, thread_id=thread.id, auth_context=auth
    )
    await start.ainvoke({"message": "m", "cron": _CRON, "timezone": _TZ})

    stop = create_stop_watch_tool(
        workspace_id=db_workspace.id, thread_id=thread.id, auth_context=auth
    )
    out = await stop.ainvoke({})

    assert out["status"] == "stopped"
    assert out["count"] == 1

    service = AutomationService(session=db_session, auth=auth)
    found = await find_watches_for_thread(
        service, workspace_id=db_workspace.id, thread_id=thread.id
    )
    assert found == []


async def test_stop_watch_tool_reports_not_watching_when_none(
    tools_use_test_session,
    db_workspace: Workspace,
    db_user: User,
    thread: NewChatThread,
) -> None:
    stop = create_stop_watch_tool(
        workspace_id=db_workspace.id,
        thread_id=thread.id,
        auth_context=AuthContext.session(db_user),
    )
    out = await stop.ainvoke({})
    assert out["status"] == "not_watching"


async def test_refresh_watch_tool_enqueues_a_run(
    tools_use_test_session,
    enqueue_spy: list[dict],
    db_session: AsyncSession,
    db_user: User,
    db_workspace: Workspace,
    thread: NewChatThread,
) -> None:
    _billable(db_workspace)
    await db_session.flush()
    auth = AuthContext.session(db_user)

    start = create_start_watch_tool(
        workspace_id=db_workspace.id, thread_id=thread.id, auth_context=auth
    )
    started = await start.ainvoke({"message": "m", "cron": _CRON, "timezone": _TZ})

    refresh = create_refresh_watch_tool(
        workspace_id=db_workspace.id, thread_id=thread.id, auth_context=auth
    )
    out = await refresh.ainvoke({})

    assert out["status"] == "refreshing"
    assert out["refreshed_ids"] == [started["automation_id"]]
    assert len(enqueue_spy) == 1


async def test_tools_error_without_thread_or_auth() -> None:
    tool = create_start_watch_tool(
        workspace_id=1, thread_id=None, auth_context=None
    )
    out = await tool.ainvoke({"message": "m", "cron": _CRON, "timezone": _TZ})
    assert out["status"] == "error"
