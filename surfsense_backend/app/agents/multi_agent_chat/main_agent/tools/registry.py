"""SRP main-agent tool registry.

The main agent exposes only a small, fixed set of SurfSense tools to its LLM;
connector integrations, MCP, and deliverables are delegated to ``task``
subagents (see :mod:`app.agents.multi_agent_chat.main_agent.tools.index`).

This module is the *building* counterpart to that name list: it owns the
factories for those few tools and nothing else, so the main agent's tool
surface stays self-contained and connector-free.

Tool *display* metadata for the whole app (the ``/agent/tools`` listing
endpoint) lives separately in :mod:`app.agents.shared.tools.catalog`, a
pure-data module that imports no connectors. This registry only governs what
the main agent actually builds and binds.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import BaseTool

from app.agents.shared.tools.web_search import create_web_search_tool
from app.db import ChatVisibility

from .scrape_webpage import create_scrape_webpage_tool
from .update_memory import (
    create_update_memory_tool,
    create_update_team_memory_tool,
)


def _build_scrape_webpage_tool(deps: dict[str, Any]) -> BaseTool:
    return create_scrape_webpage_tool(firecrawl_api_key=deps.get("firecrawl_api_key"))


def _build_web_search_tool(deps: dict[str, Any]) -> BaseTool:
    return create_web_search_tool(
        search_space_id=deps.get("search_space_id"),
        available_connectors=deps.get("available_connectors"),
    )


def _build_create_automation_tool(deps: dict[str, Any]) -> BaseTool:
    # Deferred import: the automation package is a sibling under ``main_agent``
    # and is only needed at build time, mirroring the shared registry's
    # call-time import to keep module import order robust.
    from .automation import create_create_automation_tool

    return create_create_automation_tool(
        search_space_id=deps["search_space_id"],
        user_id=deps["user_id"],
        llm=deps["llm"],
    )


def _build_update_memory_tool(deps: dict[str, Any]) -> BaseTool:
    if deps["thread_visibility"] == ChatVisibility.SEARCH_SPACE:
        return create_update_team_memory_tool(
            search_space_id=deps["search_space_id"],
            db_session=deps["db_session"],
            llm=deps.get("llm"),
        )
    return create_update_memory_tool(
        user_id=deps["user_id"],
        db_session=deps["db_session"],
        llm=deps.get("llm"),
    )


# Ordered to match the historical main-agent binding order:
# scrape_webpage, web_search, create_automation, update_memory.
# Each entry is ``(factory, required_dependency_names)``.
_MAIN_AGENT_TOOL_FACTORIES: dict[
    str, tuple[Callable[[dict[str, Any]], BaseTool], tuple[str, ...]]
] = {
    "scrape_webpage": (_build_scrape_webpage_tool, ()),
    "web_search": (_build_web_search_tool, ()),
    "create_automation": (
        _build_create_automation_tool,
        ("search_space_id", "user_id", "llm"),
    ),
    "update_memory": (
        _build_update_memory_tool,
        ("user_id", "search_space_id", "db_session", "thread_visibility", "llm"),
    ),
}


def build_main_agent_tools(
    dependencies: dict[str, Any],
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: list[BaseTool] | None = None,
) -> list[BaseTool]:
    """Build the main agent's tool instances.

    Args:
        dependencies: Dependency bag passed to each tool factory.
        enabled_tools: Explicit allow-list of tool names. When ``None``, all
            main-agent tools are enabled. Names not owned by this registry are
            ignored.
        disabled_tools: Names to drop after the enabled set is resolved.
        additional_tools: Extra tools appended verbatim (e.g. custom tools).

    Returns:
        Tool instances in the registry's declaration order, with any
        ``additional_tools`` appended.
    """
    if enabled_tools is None:
        names = list(_MAIN_AGENT_TOOL_FACTORIES)
    else:
        wanted = set(enabled_tools)
        names = [n for n in _MAIN_AGENT_TOOL_FACTORIES if n in wanted]

    if disabled_tools:
        disabled = set(disabled_tools)
        names = [n for n in names if n not in disabled]

    tools: list[BaseTool] = []
    for name in names:
        factory, requires = _MAIN_AGENT_TOOL_FACTORIES[name]
        missing = [dep for dep in requires if dep not in dependencies]
        if missing:
            msg = f"Tool '{name}' requires dependencies: {missing}"
            raise ValueError(msg)
        tools.append(factory(dependencies))

    if additional_tools:
        tools.extend(additional_tools)

    return tools
