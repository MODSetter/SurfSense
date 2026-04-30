"""Confluence domain agent graph."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.expert_agent.connectors.confluence as confluence_pkg
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.core.agents import build_domain_agent


def build_confluence_domain_agent(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Compiled Confluence domain-agent graph."""
    return build_domain_agent(
        llm,
        tools,
        prompt_package=confluence_pkg.__name__,
        prompt_stem="domain_prompt",
    )
