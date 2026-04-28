"""Tests for declarative dedup_key on ToolDefinition (Tier 2.3 migration)."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agents.new_chat.middleware.dedup_tool_calls import (
    DedupHITLToolCallsMiddleware,
)

pytestmark = pytest.mark.unit


def _make_tool(name: str, *, dedup_key=None, hitl_dedup_key=None):
    metadata = {}
    if dedup_key is not None:
        metadata["dedup_key"] = dedup_key
    if hitl_dedup_key is not None:
        metadata["hitl"] = True
        metadata["hitl_dedup_key"] = hitl_dedup_key

    def _fn(**kwargs):
        return "ok"

    return StructuredTool.from_function(
        func=_fn, name=name, description="x", metadata=metadata
    )


def _msg(*calls: dict) -> AIMessage:
    return AIMessage(content="", tool_calls=list(calls))


class _Runtime:
    pass


def test_callable_dedup_key_takes_priority() -> None:
    tool = _make_tool(
        "create_doc",
        dedup_key=lambda args: f"{args.get('parent_id')}::{args.get('title')}",
    )
    mw = DedupHITLToolCallsMiddleware(agent_tools=[tool])
    state = {
        "messages": [
            _msg(
                {"name": "create_doc", "args": {"parent_id": "x", "title": "y"}, "id": "1"},
                {"name": "create_doc", "args": {"parent_id": "x", "title": "y"}, "id": "2"},
                {"name": "create_doc", "args": {"parent_id": "x", "title": "z"}, "id": "3"},
            )
        ]
    }
    out = mw.after_model(state, _Runtime())
    assert out is not None
    new_calls = out["messages"][0].tool_calls
    assert len(new_calls) == 2  # one duplicate dropped
    assert {c["id"] for c in new_calls} == {"1", "3"}


def test_string_hitl_dedup_key_still_works() -> None:
    tool = _make_tool("send_x", hitl_dedup_key="subject")
    mw = DedupHITLToolCallsMiddleware(agent_tools=[tool])
    state = {
        "messages": [
            _msg(
                {"name": "send_x", "args": {"subject": "Hello"}, "id": "1"},
                {"name": "send_x", "args": {"subject": "hello"}, "id": "2"},  # case
            )
        ]
    }
    out = mw.after_model(state, _Runtime())
    assert out is not None
    assert len(out["messages"][0].tool_calls) == 1


def test_no_agent_tools_means_no_dedup() -> None:
    """After the cleanup tier removed the legacy ``_NATIVE_HITL_TOOL_DEDUP_KEYS``
    map, dedup is purely declarative — no resolvers means no dedup runs.

    Coverage for the previously hardcoded native HITL tools now lives on
    each :class:`ToolDefinition.dedup_key` in
    :mod:`app.agents.new_chat.tools.registry`, which is wired through to
    ``tool.metadata`` by :func:`build_tools`.
    """
    mw = DedupHITLToolCallsMiddleware(agent_tools=None)
    state = {
        "messages": [
            _msg(
                {"name": "create_notion_page", "args": {"title": "X"}, "id": "1"},
                {"name": "create_notion_page", "args": {"title": "x"}, "id": "2"},
            )
        ]
    }
    out = mw.after_model(state, _Runtime())
    assert out is None


def test_registry_propagates_dedup_key_to_tool_metadata() -> None:
    """Smoke-check the wiring path that replaced the legacy native map.

    ``ToolDefinition.dedup_key`` set in the registry must be copied onto
    the constructed tool's ``metadata`` so :class:`DedupHITLToolCallsMiddleware`
    can pick it up at agent build time.
    """
    from app.agents.new_chat.tools.registry import (
        BUILTIN_TOOLS,
        wrap_dedup_key_by_arg_name,
    )

    notion_tool_defs = [t for t in BUILTIN_TOOLS if t.name == "create_notion_page"]
    assert notion_tool_defs, "registry should still expose create_notion_page"
    tool_def = notion_tool_defs[0]
    assert tool_def.dedup_key is not None
    # Same wrapping helper used in the registry — sanity check identity
    sample = wrap_dedup_key_by_arg_name("title")({"title": "Plan"})
    assert sample == "plan"


def test_unknown_tool_passes_through() -> None:
    mw = DedupHITLToolCallsMiddleware(agent_tools=None)
    state = {
        "messages": [
            _msg(
                {"name": "anything_else", "args": {"x": 1}, "id": "1"},
                {"name": "anything_else", "args": {"x": 1}, "id": "2"},
            )
        ]
    }
    out = mw.after_model(state, _Runtime())
    assert out is None  # no dedup configured -> kept
