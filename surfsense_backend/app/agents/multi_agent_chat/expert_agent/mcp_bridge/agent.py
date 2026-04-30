"""Domain agents for MCP-only OAuth integrations (no native registry slice)."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.expert_agent.mcp_bridge as mcp_bridge_pkg
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.core.agents import build_domain_agent


def build_mcp_route_domain_agent(
    llm: BaseChatModel,
    route_key: str,
    tools: Sequence[BaseTool],
):
    """One subgraph per MCP-only route (``linear``, ``slack``, …); prompt stem ``{route_key}_domain``."""
    return build_domain_agent(
        llm,
        tools,
        prompt_package=mcp_bridge_pkg.__name__,
        prompt_stem=f"{route_key}_domain",
    )
