"""Cross-cutting building blocks (prompts, agents, delegation, registry) — not domain logic."""

from app.agents.multi_agent_chat.core.agents import build_domain_agent
from app.agents.multi_agent_chat.core.bindings import connector_binding
from app.agents.multi_agent_chat.core.delegation import compose_child_task
from app.agents.multi_agent_chat.core.invocation import extract_last_assistant_text
from app.agents.multi_agent_chat.core.prompts import read_prompt_md
from app.agents.multi_agent_chat.core.registry import (
    REGISTRY_ROUTING_CATEGORY_KEYS,
    TOOL_NAMES_BY_CATEGORY,
    build_registry_dependencies,
    build_registry_tools_for_category,
)

__all__ = [
    "REGISTRY_ROUTING_CATEGORY_KEYS",
    "TOOL_NAMES_BY_CATEGORY",
    "build_domain_agent",
    "build_registry_dependencies",
    "build_registry_tools_for_category",
    "compose_child_task",
    "connector_binding",
    "extract_last_assistant_text",
    "read_prompt_md",
]
