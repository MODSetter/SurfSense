"""Registry-backed research tools (web, scrape, SurfSense docs help)."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.core.registry import build_registry_tools_for_category


def build_research_tools(dependencies: dict[str, Any]) -> list[BaseTool]:
    """Tools from ``new_chat`` registry: ``research`` category."""
    return build_registry_tools_for_category(dependencies, "research")
