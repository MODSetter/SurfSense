"""Google Calendar domain agent graph."""

from __future__ import annotations

from collections.abc import Sequence

import app.agents.multi_agent_chat.calendar as calendar_pkg
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.shared.domain_agent_factory import build_domain_agent


def build_calendar_domain_agent(llm: BaseChatModel, tools: Sequence[BaseTool]):
    """Compiled Calendar domain-agent graph (prompt + tools co-located under ``calendar``)."""
    return build_domain_agent(
        llm,
        tools,
        prompt_package=calendar_pkg.__name__,
        prompt_stem="domain_prompt",
    )
