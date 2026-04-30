"""Google Calendar vertical slice: connector tools, domain agent, ``domain_prompt.md``."""

from app.agents.multi_agent_chat.expert_agent.connectors.calendar.agent import build_calendar_domain_agent
from app.agents.multi_agent_chat.expert_agent.connectors.calendar.slice_tools import (
    build_calendar_tools,
)

__all__ = [
    "build_calendar_domain_agent",
    "build_calendar_tools",
]
