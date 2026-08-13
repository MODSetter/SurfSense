"""``task.subagent_type`` is schema-constrained to the live roster.

Guards three properties: the provider-facing schema advertises the roster as an
enum, paused legacy-alias checkpoints still resolve (accepted-but-hidden), and an
off-roster name comes back as a model-readable error instead of crashing.
"""

from __future__ import annotations

import pytest
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.function_calling import convert_to_openai_tool

from app.agents.chat.multi_agent_chat.main_agent.middleware.checkpointed_subagent_middleware.task_tool import (
    build_task_tool_with_parent_config,
)

pytestmark = pytest.mark.unit


def _tool(names: list[str]):
    sub = RunnableLambda(lambda s: {"messages": []})
    return build_task_tool_with_parent_config(
        [{"name": n, "description": n, "runnable": sub} for n in names]
    )


def _subagent_type_enum(tool) -> list[str] | None:
    prop = convert_to_openai_tool(tool)["function"]["parameters"]["properties"][
        "subagent_type"
    ]
    if "enum" in prop:
        return prop["enum"]
    for branch in prop.get("anyOf", []):
        if "enum" in branch:
            return branch["enum"]
    return None


def test_subagent_type_advertises_roster_enum() -> None:
    tool = _tool(["knowledge_base", "web_crawler"])

    assert _subagent_type_enum(tool) == ["knowledge_base", "web_crawler"]


def test_legacy_alias_resolves_to_roster_and_stays_hidden() -> None:
    tool = _tool(["mcp_discovery"])

    assert tool.args_schema(subagent_type="gmail").subagent_type == "mcp_discovery"
    assert "gmail" not in (_subagent_type_enum(tool) or [])


def test_off_roster_name_returns_model_readable_error() -> None:
    tool = _tool(["knowledge_base"])

    out = tool.invoke(
        {
            "name": "task",
            "args": {"description": "x", "subagent_type": "does_not_exist"},
            "id": "call_1",
            "type": "tool_call",
        }
    )

    assert out.status == "error"
    assert "knowledge_base" in out.content
