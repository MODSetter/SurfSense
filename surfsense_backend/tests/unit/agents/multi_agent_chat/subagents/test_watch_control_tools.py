"""Unit tests for the ``stop_watch`` and ``refresh_watch`` chat tools.

Both act on the *current* chat: they look up the watches bound to this thread
and stop them / run them now. The watch service + session are faked so no DB is
touched.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


class _FakeSessionCM:
    async def __aenter__(self) -> Any:
        return MagicMock(name="session")

    async def __aexit__(self, *_exc: Any) -> bool:
        return False


def _watch(automation_id: int) -> Any:
    a = MagicMock()
    a.id = automation_id
    return a


@pytest.mark.asyncio
async def test_stop_watch_stops_every_watch_on_the_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.intelligence_agent.tools import (
        stop_watch as mod,
    )

    monkeypatch.setattr(mod, "AutomationService", MagicMock(return_value="svc"))
    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCM())
    monkeypatch.setattr(
        mod, "find_watches_for_thread", AsyncMock(return_value=[_watch(1), _watch(2)])
    )
    stop_service = AsyncMock()
    monkeypatch.setattr(mod, "stop_watch_service", stop_service)

    tool = mod.create_stop_watch_tool(
        workspace_id=3, thread_id=55, auth_context=MagicMock()
    )
    out = await tool.ainvoke({})

    assert out["status"] == "stopped"
    assert sorted(out["stopped_ids"]) == [1, 2]
    assert stop_service.await_count == 2


@pytest.mark.asyncio
async def test_stop_watch_reports_when_nothing_to_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.intelligence_agent.tools import (
        stop_watch as mod,
    )

    monkeypatch.setattr(mod, "AutomationService", MagicMock(return_value="svc"))
    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCM())
    monkeypatch.setattr(mod, "find_watches_for_thread", AsyncMock(return_value=[]))
    monkeypatch.setattr(mod, "stop_watch_service", AsyncMock())

    tool = mod.create_stop_watch_tool(
        workspace_id=3, thread_id=55, auth_context=MagicMock()
    )
    out = await tool.ainvoke({})

    assert out["status"] == "not_watching"


@pytest.mark.asyncio
async def test_refresh_watch_runs_each_watch_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.intelligence_agent.tools import (
        refresh_watch as mod,
    )

    monkeypatch.setattr(mod, "AutomationService", MagicMock(return_value="svc"))
    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCM())
    monkeypatch.setattr(
        mod, "find_watches_for_thread", AsyncMock(return_value=[_watch(7)])
    )
    run_now = AsyncMock()
    monkeypatch.setattr(mod, "run_watch_now", run_now)

    tool = mod.create_refresh_watch_tool(
        workspace_id=3, thread_id=55, auth_context=MagicMock()
    )
    out = await tool.ainvoke({})

    assert out["status"] == "refreshing"
    assert out["refreshed_ids"] == [7]
    run_now.assert_awaited_once()
    assert run_now.await_args.kwargs["automation_id"] == 7


def test_load_tools_includes_control_tools_when_bindable() -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.intelligence_agent.tools.index import (
        load_tools,
    )

    tools = load_tools(
        dependencies={
            "workspace_id": 3,
            "thread_id": 55,
            "auth_context": MagicMock(),
        }
    )
    names = {t.name for t in tools}
    assert {"start_watch", "stop_watch", "refresh_watch"} <= names
