"""Unit tests for the ``start_watch`` tool on the scraping sub-agent.

``start_watch`` binds a recurring watch to the *current* chat: it distils the
question + cadence the agent extracted and creates a ``schedule`` +
``chat_message`` automation via the watch service. These tests fake the watch
service / session so no DB is touched; they pin that the tool forwards the
current chat id + system auth and reports a clear outcome.
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


def _patch_deps(monkeypatch: pytest.MonkeyPatch, *, created: Any) -> AsyncMock:
    from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools import (
        start_watch as mod,
    )

    fake_create_watch = AsyncMock(return_value=created)
    monkeypatch.setattr(mod, "create_watch", fake_create_watch)
    monkeypatch.setattr(mod, "AutomationService", MagicMock(return_value="svc"))
    monkeypatch.setattr(mod, "async_session_maker", lambda: _FakeSessionCM())
    return fake_create_watch


@pytest.mark.asyncio
async def test_start_watch_binds_watch_to_current_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools import (
        start_watch as mod,
    )

    created = MagicMock(id=123)
    created.name = "Watch: prices"
    fake_create_watch = _patch_deps(monkeypatch, created=created)

    auth = MagicMock()
    tool = mod.create_start_watch_tool(workspace_id=3, thread_id=55, auth_context=auth)

    out = await tool.ainvoke(
        {"message": "what changed on prices?", "cron": "0 9 * * 1-5", "timezone": "UTC"}
    )

    assert out["status"] == "watching"
    assert out["automation_id"] == 123

    fake_create_watch.assert_awaited_once()
    kwargs = fake_create_watch.await_args.kwargs
    assert kwargs["workspace_id"] == 3
    assert kwargs["thread_id"] == 55
    assert kwargs["message"] == "what changed on prices?"
    assert kwargs["cron"] == "0 9 * * 1-5"
    assert kwargs["timezone"] == "UTC"

    # The service is constructed with the passed-through auth context.
    assert mod.AutomationService.call_args.kwargs["auth"] is auth


@pytest.mark.asyncio
async def test_start_watch_errors_without_thread_or_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools import (
        start_watch as mod,
    )

    fake_create_watch = _patch_deps(monkeypatch, created=MagicMock(id=1))

    no_thread = mod.create_start_watch_tool(
        workspace_id=3, thread_id=None, auth_context=MagicMock()
    )
    out_no_thread = await no_thread.ainvoke(
        {"message": "x", "cron": "0 9 * * *", "timezone": "UTC"}
    )
    assert out_no_thread["status"] == "error"

    no_auth = mod.create_start_watch_tool(
        workspace_id=3, thread_id=55, auth_context=None
    )
    out_no_auth = await no_auth.ainvoke(
        {"message": "x", "cron": "0 9 * * *", "timezone": "UTC"}
    )
    assert out_no_auth["status"] == "error"

    fake_create_watch.assert_not_awaited()


def test_load_tools_includes_start_watch_only_when_bindable() -> None:
    from app.agents.chat.multi_agent_chat.subagents.builtins.scraping.tools.index import (
        load_tools,
    )

    bindable = load_tools(
        dependencies={
            "workspace_id": 3,
            "thread_id": 55,
            "auth_context": MagicMock(),
        }
    )
    assert "start_watch" in {t.name for t in bindable}

    not_bindable = load_tools(dependencies={"workspace_id": 3})
    assert "start_watch" not in {t.name for t in not_bindable}
