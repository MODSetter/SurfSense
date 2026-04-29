"""Gmail domain agent graph."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.gmail as gmail_pkg
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.shared.domain_agent_factory import build_domain_agent


def build_gmail_domain_agent(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Compiled Gmail domain-agent graph (prompt + tools co-located under ``gmail``)."""
    return build_domain_agent(
        llm,
        tools,
        prompt_package=gmail_pkg.__name__,
        prompt_stem="domain_prompt",
    )
