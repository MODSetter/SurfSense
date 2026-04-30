"""Main chat tool registry grouping + dependency bundles for domain slices."""

from app.agents.multi_agent_chat.core.registry.categories import (
    REGISTRY_ROUTING_CATEGORY_KEYS,
    TOOL_NAMES_BY_CATEGORY,
)
from app.agents.multi_agent_chat.core.registry.dependencies import build_registry_dependencies
from app.agents.multi_agent_chat.core.registry.subset import build_registry_tools_for_category

__all__ = [
    "REGISTRY_ROUTING_CATEGORY_KEYS",
    "TOOL_NAMES_BY_CATEGORY",
    "build_registry_dependencies",
    "build_registry_tools_for_category",
]
