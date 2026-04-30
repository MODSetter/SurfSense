"""Registry-backed Google Drive tools."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.core.registry import build_registry_tools_for_category


def build_google_drive_tools(dependencies: dict[str, Any]) -> list[BaseTool]:
    """Registry-backed tools for the ``google_drive`` category."""
    return build_registry_tools_for_category(dependencies, "google_drive")
