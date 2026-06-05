"""``memory`` route: ``SurfSenseSubagentSpec`` builder for deepagents."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.chat.multi_agent_chat.subagents.shared.md_file_reader import (
    read_md_file,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import SurfSenseSubagentSpec
from app.agents.chat.multi_agent_chat.subagents.shared.subagent_builder import (
    pack_subagent,
)

from .tools.index import NAME, RULESET, load_tools


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    mcp_tools: list[BaseTool] | None = None,
) -> SurfSenseSubagentSpec:
    tools = [*load_tools(dependencies=dependencies), *(mcp_tools or [])]
    description = (
        read_md_file(__package__, "description").strip()
        or "Handles memory tasks for this workspace."
    )
    system_prompt = read_md_file(__package__, "system_prompt").strip()
    return pack_subagent(
        name=NAME,
        description=description,
        system_prompt=system_prompt,
        tools=tools,
        ruleset=RULESET,
        dependencies=dependencies,
        model=model,
        middleware_stack=middleware_stack,
    )
