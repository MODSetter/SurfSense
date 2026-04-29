"""Gmail vertical slice: connector tools, domain agent, ``domain_prompt.md``."""

from app.agents.multi_agent_chat.gmail.agent import build_gmail_domain_agent
from app.agents.multi_agent_chat.gmail.connector_tools import build_gmail_connector_tools

__all__ = [
    "build_gmail_connector_tools",
    "build_gmail_domain_agent",
]
