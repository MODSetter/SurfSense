"""`notion` route: ``SubAgent`` spec for deepagents."""

from __future__ import annotations

from typing import Any

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_chat.subagents.shared.hitl.approvals.middleware_gated import (
    middleware_gated_interrupt_on,
)
from app.agents.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)
from app.agents.multi_agent_chat.subagents.shared.tool_kinds import (
    ToolsPermissions,
    merge_tools_permissions,
)

from .tools.index import load_tools

NAME = "notion"


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    extra_tools_bucket: ToolsPermissions | None = None,
) -> SubAgent:
    buckets = load_tools(dependencies=dependencies)
    merged_tools_bucket = merge_tools_permissions(buckets, extra_tools_bucket)
    tools = [
        row["tool"]
        for row in (*merged_tools_bucket["allow"], *merged_tools_bucket["ask"])
        if row.get("tool") is not None
    ]
    interrupt_on = middleware_gated_interrupt_on(merged_tools_bucket)
    description = read_md_file(__package__, "description").strip()
    if not description:
        description = "Handles notion tasks for this workspace."
    system_prompt = read_md_file(__package__, "system_prompt").strip()
    return pack_subagent(
        name=NAME,
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        interrupt_on=interrupt_on,
        model=model,
        middleware_stack=middleware_stack,
    )
