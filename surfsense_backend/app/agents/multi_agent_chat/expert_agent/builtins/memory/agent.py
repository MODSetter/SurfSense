"""Memory domain agent graph."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.expert_agent.builtins.memory as memory_pkg
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.core.agents import build_domain_agent


def build_memory_domain_agent(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Compiled memory domain-agent graph."""
    return build_domain_agent(
        llm,
        tools,
        prompt_package=memory_pkg.__name__,
        prompt_stem="domain_prompt",
    )
