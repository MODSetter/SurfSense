"""Supervisor routing: domain-agent wrappers and composed routing tool lists."""

from app.agents.multi_agent_chat.routing.from_domain_agents import routing_tools_from_domain_agents
from app.agents.multi_agent_chat.routing.supervisor_routing import build_supervisor_routing_tools
from app.agents.multi_agent_chat.shared.invoke_output import extract_last_assistant_text

__all__ = [
    "build_supervisor_routing_tools",
    "extract_last_assistant_text",
    "routing_tools_from_domain_agents",
]
