"""Discord vertical slice: registry tools, domain agent, ``domain_prompt.md``."""

from app.agents.multi_agent_chat.expert_agent.connectors.discord.agent import build_discord_domain_agent
from app.agents.multi_agent_chat.expert_agent.connectors.discord.slice_tools import build_discord_tools

__all__ = [
    "build_discord_tools",
    "build_discord_domain_agent",
]
