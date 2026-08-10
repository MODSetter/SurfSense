"""Tests for ToolCallNameRepairMiddleware."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from app.agents.chat.multi_agent_chat.main_agent.middleware.tool_call_repair.builder import (
    build_repair_mw,
)
from app.agents.chat.multi_agent_chat.main_agent.middleware.tool_call_repair.middleware import (
    ToolCallNameRepairMiddleware,
)
from app.agents.chat.multi_agent_chat.main_agent.tools.invalid_tool import (
    INVALID_TOOL_NAME,
)
from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags

pytestmark = pytest.mark.unit


def _make_state(message: AIMessage) -> dict:
    return {"messages": [message]}


class _FakeRuntime:
    def __init__(self, context: object | None = None) -> None:
        self.context = context


class TestRepair:
    def test_passthrough_when_name_matches(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "echo", "args": {}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is None  # no change

    def test_lowercase_repair(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "Echo", "args": {"x": 1}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired = out["messages"][0]
        assert repaired.tool_calls[0]["name"] == "echo"

    def test_invalid_fallback_when_no_match(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo", INVALID_TOOL_NAME},
            fuzzy_match_threshold=None,
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "totally_different_name", "args": {"k": "v"}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        repaired_call = out["messages"][0].tool_calls[0]
        assert repaired_call["name"] == INVALID_TOOL_NAME
        assert repaired_call["args"]["tool"] == "totally_different_name"
        assert "totally_different_name" in repaired_call["args"]["error"]

    def test_no_invalid_means_skip_when_unknown(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "unknown", "args": {}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        # No repair available; original returned unchanged (no update)
        assert out is None

    def test_fuzzy_match_works_when_enabled(self) -> None:
        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"search_documents"},
            fuzzy_match_threshold=0.7,
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search_docments", "args": {}, "id": "1"},
            ],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        assert out["messages"][0].tool_calls[0]["name"] == "search_documents"

    def test_skips_when_no_messages(self) -> None:
        mw = ToolCallNameRepairMiddleware(registered_tool_names={"echo"})
        out = mw.after_model({"messages": []}, _FakeRuntime())
        assert out is None

    def test_unbound_deepagent_builtin_routes_to_invalid(self) -> None:
        """A router never binds FS builtins (ls/read_file/…); they must self-correct.

        Previously the builder marked all deepagents builtins as "known", so a
        ``read_file`` call passed repair and then dispatch-failed. It must route
        to ``invalid`` instead.
        """
        tools = [
            SimpleNamespace(name="search_knowledge_base"),
            SimpleNamespace(name=INVALID_TOOL_NAME),
        ]
        mw = build_repair_mw(flags=AgentFeatureFlags(), tools=tools)
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "read_file", "args": {"path": "/x"}, "id": "1"}],
        )
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is not None
        assert out["messages"][0].tool_calls[0]["name"] == INVALID_TOOL_NAME

    @pytest.mark.parametrize("name", ["task", "write_todos"])
    def test_middleware_bound_tools_stay_known(self, name: str) -> None:
        """``task``/``write_todos`` are bound via middleware, not ``tools`` — keep them known."""
        mw = build_repair_mw(
            flags=AgentFeatureFlags(),
            tools=[SimpleNamespace(name=INVALID_TOOL_NAME)],
        )
        msg = AIMessage(content="", tool_calls=[{"name": name, "args": {}, "id": "1"}])
        out = mw.after_model(_make_state(msg), _FakeRuntime())
        assert out is None  # recognized, not rewritten to invalid

    def test_runtime_context_extends_registered(self) -> None:
        from types import SimpleNamespace

        mw = ToolCallNameRepairMiddleware(
            registered_tool_names={"echo"}, fuzzy_match_threshold=None
        )
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "DynamicTool", "args": {}, "id": "1"},
            ],
        )
        runtime = _FakeRuntime(SimpleNamespace(registered_tool_names=["dynamictool"]))
        out = mw.after_model(_make_state(msg), runtime)
        assert out is not None
        assert out["messages"][0].tool_calls[0]["name"] == "dynamictool"
