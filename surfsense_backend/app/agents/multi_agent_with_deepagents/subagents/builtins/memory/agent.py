"""`memory` route: ``SubAgent`` spec for deepagents."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent
from langchain_core.language_models import BaseChatModel

from app.agents.multi_agent_with_deepagents.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
    merge_tools_permissions,
    middleware_gated_interrupt_on,
)
from app.agents.multi_agent_with_deepagents.subagents.shared.subagent_builder import (
    pack_subagent,
)

from .tools.index import load_tools

NAME = "memory"


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    extra_middleware: Sequence[Any] | None = None,
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
        description = "Handles memory tasks for this workspace."
    system_prompt = read_md_file(__package__, "system_prompt").strip()
    return pack_subagent(
        name=NAME,
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        interrupt_on=interrupt_on,
        model=model,
        extra_middleware=extra_middleware,
    )
