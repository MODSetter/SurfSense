"""Unit tests for ActionLogMiddleware (Tier 5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.middleware.action_log import ActionLogMiddleware
from app.agents.new_chat.tools.registry import ToolDefinition


@dataclass
class _FakeRequest:
    """Minimal stand-in for ToolCallRequest used in unit tests."""

    tool_call: dict[str, Any]
    tool: Any = None
    state: Any = None
    runtime: Any = None


@tool
def make_widget(color: str, size: int) -> str:
    """Create a widget."""
    return f"made {color} {size}"


def _enabled_flags(**overrides: bool) -> AgentFeatureFlags:
    return AgentFeatureFlags(
        disable_new_agent_stack=False,
        enable_action_log=True,
        **overrides,
    )


def _disabled_flags() -> AgentFeatureFlags:
    return AgentFeatureFlags(disable_new_agent_stack=False, enable_action_log=False)


@pytest.fixture
def patch_get_flags():
    def _patch(flags: AgentFeatureFlags):
        return patch(
            "app.agents.new_chat.middleware.action_log.get_flags",
            return_value=flags,
        )

    return _patch


@pytest.fixture
def fake_session_factory():
    """Patch ``shielded_async_session`` with a recording fake."""
    captured: dict[str, list] = {"rows": []}

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def add(self, row):
            captured["rows"].append(row)

        async def commit(self):
            captured["committed"] = True

    def _factory():
        return _FakeSession()

    return captured, _factory


class TestActionLogMiddlewareDisabled:
    @pytest.mark.asyncio
    async def test_no_op_when_flag_off(self, patch_get_flags) -> None:
        mw = ActionLogMiddleware(thread_id=1, search_space_id=1, user_id=None)
        request = _FakeRequest(
            tool_call={
                "name": "make_widget",
                "args": {"color": "red", "size": 1},
                "id": "tc1",
            }
        )
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="tc1"))
        with patch_get_flags(_disabled_flags()):
            result = await mw.awrap_tool_call(request, handler)
        handler.assert_awaited_once()
        assert isinstance(result, ToolMessage)

    @pytest.mark.asyncio
    async def test_no_op_when_thread_id_none(self, patch_get_flags) -> None:
        mw = ActionLogMiddleware(thread_id=None, search_space_id=1, user_id=None)
        request = _FakeRequest(
            tool_call={"name": "make_widget", "args": {}, "id": "tc1"}
        )
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="tc1"))
        with patch_get_flags(_enabled_flags()):
            result = await mw.awrap_tool_call(request, handler)
        assert isinstance(result, ToolMessage)


class TestActionLogMiddlewarePersistence:
    @pytest.mark.asyncio
    async def test_writes_row_on_success(
        self, patch_get_flags, fake_session_factory
    ) -> None:
        captured, factory = fake_session_factory
        mw = ActionLogMiddleware(thread_id=42, search_space_id=7, user_id="u1")
        request = _FakeRequest(
            tool_call={
                "name": "make_widget",
                "args": {"color": "red", "size": 3},
                "id": "tc-abc",
            },
        )
        result_msg = ToolMessage(content="ok", tool_call_id="tc-abc", id="msg-1")
        handler = AsyncMock(return_value=result_msg)

        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=lambda: factory()),
        ):
            result = await mw.awrap_tool_call(request, handler)

        assert result is result_msg
        assert len(captured["rows"]) == 1
        row = captured["rows"][0]
        assert row.thread_id == 42
        assert row.search_space_id == 7
        assert row.user_id == "u1"
        assert row.tool_name == "make_widget"
        assert row.args == {"color": "red", "size": 3}
        assert row.result_id == "msg-1"
        assert row.error is None
        assert row.reverse_descriptor is None
        assert row.reversible is False

    @pytest.mark.asyncio
    async def test_writes_row_on_failure_and_reraises(
        self, patch_get_flags, fake_session_factory
    ) -> None:
        captured, factory = fake_session_factory
        mw = ActionLogMiddleware(thread_id=42, search_space_id=7, user_id="u1")
        request = _FakeRequest(
            tool_call={"name": "make_widget", "args": {"color": "red"}, "id": "tc1"}
        )
        handler = AsyncMock(side_effect=ValueError("boom"))

        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=lambda: factory()),
            pytest.raises(ValueError, match="boom"),
        ):
            await mw.awrap_tool_call(request, handler)

        assert len(captured["rows"]) == 1
        row = captured["rows"][0]
        assert row.tool_name == "make_widget"
        assert row.error == {"type": "ValueError", "message": "boom"}
        assert row.result_id is None

    @pytest.mark.asyncio
    async def test_persistence_failure_does_not_break_tool_call(
        self, patch_get_flags
    ) -> None:
        """Even if the DB write blows up, the tool's result must reach the model."""
        mw = ActionLogMiddleware(thread_id=1, search_space_id=1, user_id=None)
        request = _FakeRequest(
            tool_call={"name": "make_widget", "args": {}, "id": "tc1"}
        )
        result_msg = ToolMessage(content="ok", tool_call_id="tc1")
        handler = AsyncMock(return_value=result_msg)

        def _exploding_session():
            raise RuntimeError("DB is down")

        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=_exploding_session),
        ):
            result = await mw.awrap_tool_call(request, handler)
        assert result is result_msg


class TestReverseDescriptor:
    @pytest.mark.asyncio
    async def test_renders_reverse_descriptor_when_tool_declares_one(
        self, patch_get_flags, fake_session_factory
    ) -> None:
        captured, factory = fake_session_factory

        def _reverse(args, result):
            return {"tool": "delete_widget", "args": {"id": result["id"]}}

        tool_def = ToolDefinition(
            name="make_widget",
            description="Create a widget",
            factory=lambda deps: make_widget,
            reverse=_reverse,
        )
        mw = ActionLogMiddleware(
            thread_id=1,
            search_space_id=1,
            user_id="u",
            tool_definitions={"make_widget": tool_def},
        )
        request = _FakeRequest(
            tool_call={
                "name": "make_widget",
                "args": {"color": "blue", "size": 1},
                "id": "tc-xyz",
            },
        )
        result_msg = ToolMessage(
            content='{"id": "widget-9"}', tool_call_id="tc-xyz", id="msg-9"
        )
        handler = AsyncMock(return_value=result_msg)

        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=lambda: factory()),
        ):
            await mw.awrap_tool_call(request, handler)

        row = captured["rows"][0]
        assert row.reversible is True
        assert row.reverse_descriptor == {
            "tool": "delete_widget",
            "args": {"id": "widget-9"},
        }

    @pytest.mark.asyncio
    async def test_swallows_reverse_callable_errors(
        self, patch_get_flags, fake_session_factory
    ) -> None:
        captured, factory = fake_session_factory

        def _bad_reverse(args, result):
            raise RuntimeError("reverse blew up")

        tool_def = ToolDefinition(
            name="make_widget",
            description="Create a widget",
            factory=lambda deps: make_widget,
            reverse=_bad_reverse,
        )
        mw = ActionLogMiddleware(
            thread_id=1,
            search_space_id=1,
            user_id=None,
            tool_definitions={"make_widget": tool_def},
        )
        request = _FakeRequest(
            tool_call={"name": "make_widget", "args": {}, "id": "tc1"}
        )
        result_msg = ToolMessage(content="ok", tool_call_id="tc1")
        handler = AsyncMock(return_value=result_msg)

        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=lambda: factory()),
        ):
            await mw.awrap_tool_call(request, handler)

        row = captured["rows"][0]
        assert row.reversible is False
        assert row.reverse_descriptor is None

    @pytest.mark.asyncio
    async def test_no_reverse_when_tool_definition_missing(
        self, patch_get_flags, fake_session_factory
    ) -> None:
        captured, factory = fake_session_factory
        mw = ActionLogMiddleware(thread_id=1, search_space_id=1, user_id=None)
        request = _FakeRequest(
            tool_call={"name": "unknown_tool", "args": {}, "id": "tc1"}
        )
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="tc1"))
        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=lambda: factory()),
        ):
            await mw.awrap_tool_call(request, handler)
        row = captured["rows"][0]
        assert row.reversible is False


class TestArgsTruncation:
    @pytest.mark.asyncio
    async def test_huge_args_payload_is_truncated(
        self, patch_get_flags, fake_session_factory
    ) -> None:
        captured, factory = fake_session_factory
        mw = ActionLogMiddleware(thread_id=1, search_space_id=1, user_id=None)
        # Build a > 32KB string so the persisted payload triggers the truncation path.
        huge = "x" * (40 * 1024)
        request = _FakeRequest(
            tool_call={"name": "make_widget", "args": {"blob": huge}, "id": "tc1"},
        )
        handler = AsyncMock(return_value=ToolMessage(content="ok", tool_call_id="tc1"))
        with (
            patch_get_flags(_enabled_flags()),
            patch("app.db.shielded_async_session", side_effect=lambda: factory()),
        ):
            await mw.awrap_tool_call(request, handler)
        row = captured["rows"][0]
        assert row.args is not None
        assert row.args.get("_truncated") is True
        assert row.args.get("_size", 0) >= 40 * 1024
