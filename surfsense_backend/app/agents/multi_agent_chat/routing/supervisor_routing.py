"""Compose domain agents + connector tool lists into supervisor ``gmail`` / ``calendar`` routing tools."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.calendar import build_calendar_domain_agent
from app.agents.multi_agent_chat.gmail import build_gmail_domain_agent
from app.agents.multi_agent_chat.routing.from_domain_agents import routing_tools_from_domain_agents


def build_supervisor_routing_tools(
    llm: BaseChatModel,
    *,
    gmail_tools: Sequence[BaseTool] | None = None,
    calendar_tools: Sequence[BaseTool] | None = None,
) -> list[BaseTool]:
    """Domain agents (with their connector tools) → ``gmail`` / ``calendar`` routing tools."""
    gmail_domain_agent = build_gmail_domain_agent(llm, list(gmail_tools or []))
    calendar_domain_agent = build_calendar_domain_agent(llm, list(calendar_tools or []))
    return routing_tools_from_domain_agents(
        gmail_domain_agent=gmail_domain_agent,
        calendar_domain_agent=calendar_domain_agent,
    )
