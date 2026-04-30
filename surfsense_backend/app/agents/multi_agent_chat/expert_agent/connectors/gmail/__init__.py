"""Gmail vertical slice: connector tools, domain agent, ``domain_prompt.md``."""

from app.agents.multi_agent_chat.expert_agent.connectors.gmail.agent import build_gmail_domain_agent
from app.agents.multi_agent_chat.expert_agent.connectors.gmail.slice_tools import build_gmail_tools

__all__ = [
    "build_gmail_tools",
    "build_gmail_domain_agent",
]
