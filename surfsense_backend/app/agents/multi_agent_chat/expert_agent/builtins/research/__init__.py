"""Research vertical slice: registry tools, domain agent, ``domain_prompt.md``."""

from app.agents.multi_agent_chat.expert_agent.builtins.research.agent import build_research_domain_agent
from app.agents.multi_agent_chat.expert_agent.builtins.research.slice_tools import build_research_tools

__all__ = [
    "build_research_tools",
    "build_research_domain_agent",
]
