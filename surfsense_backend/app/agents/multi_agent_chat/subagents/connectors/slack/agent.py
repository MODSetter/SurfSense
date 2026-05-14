"""``slack`` route: ``SurfSenseSubagentSpec`` builder for deepagents.

Tools come exclusively from MCP. The connector's own approval ruleset is
declared in :data:`tools.index.RULESET`; the orchestrator layers it into
a per-subagent :class:`PermissionMiddleware`.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.subagents.shared.md_file_reader import read_md_file
from app.agents.multi_agent_chat.subagents.shared.spec import SurfSenseSubagentSpec
from app.agents.multi_agent_chat.subagents.shared.subagent_builder import pack_subagent

from .tools.index import NAME, RULESET


def build_subagent(
    *,
    dependencies: dict[str, Any],
    model: BaseChatModel | None = None,
    middleware_stack: dict[str, Any] | None = None,
    mcp_tools: list[BaseTool] | None = None,
) -> SurfSenseSubagentSpec:
    description = (
        read_md_file(__package__, "description").strip()
        or "Handles slack tasks for this workspace."
    )
    system_prompt = read_md_file(__package__, "system_prompt").strip()
    return pack_subagent(
        name=NAME,
        description=description,
        system_prompt=system_prompt,
        tools=list(mcp_tools or []),
        ruleset=RULESET,
        flags=dependencies["flags"],
        model=model,
        middleware_stack=middleware_stack,
    )
