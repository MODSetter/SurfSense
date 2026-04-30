"""Microsoft Teams vertical slice: registry tools, domain agent, ``domain_prompt.md``."""

from app.agents.multi_agent_chat.expert_agent.connectors.teams.agent import build_teams_domain_agent
from app.agents.multi_agent_chat.expert_agent.connectors.teams.slice_tools import build_teams_tools

__all__ = [
    "build_teams_tools",
    "build_teams_domain_agent",
]
