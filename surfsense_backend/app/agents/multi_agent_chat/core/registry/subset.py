"""Build :mod:`new_chat` registry tool subsets for multi-agent domain slices."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.new_chat.tools.registry import build_tools
from app.agents.multi_agent_chat.core.registry.categories import TOOL_NAMES_BY_CATEGORY


def build_registry_tools_for_category(
    dependencies: dict[str, Any],
    category: str,
) -> list[BaseTool]:
    """Instantiate only the tools registered for ``category`` (see ``TOOL_NAMES_BY_CATEGORY``)."""
    names = TOOL_NAMES_BY_CATEGORY.get(category)
    if not names:
        msg = f"Unknown registry category: {category!r}"
        raise ValueError(msg)
    return build_tools(dependencies, enabled_tools=names)
