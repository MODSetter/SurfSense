"""Supervisor routing: domain-agent wrappers and composed routing tool lists."""

from app.agents.multi_agent_chat.routing.domain_routing_spec import DomainRoutingSpec
from app.agents.multi_agent_chat.routing.from_domain_agents import routing_tools_from_specs
from app.agents.multi_agent_chat.routing.supervisor_routing import build_supervisor_routing_tools
from app.agents.multi_agent_chat.core.invocation import extract_last_assistant_text

__all__ = [
    "DomainRoutingSpec",
    "build_supervisor_routing_tools",
    "extract_last_assistant_text",
    "routing_tools_from_specs",
]
