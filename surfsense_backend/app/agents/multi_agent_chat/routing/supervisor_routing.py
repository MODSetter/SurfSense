"""Compose domain agents + tool lists into supervisor routing tools (one ``@tool`` per category)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.multi_agent_chat.expert_agent.builtins.deliverables import (
    build_deliverables_tools,
    build_deliverables_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.builtins.memory import (
    build_memory_tools,
    build_memory_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.builtins.research import (
    build_research_tools,
    build_research_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.calendar import (
    build_calendar_tools,
    build_calendar_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.confluence import (
    build_confluence_tools,
    build_confluence_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.discord import (
    build_discord_tools,
    build_discord_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.dropbox import (
    build_dropbox_tools,
    build_dropbox_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.gmail import (
    build_gmail_tools,
    build_gmail_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.google_drive import (
    build_google_drive_tools,
    build_google_drive_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.luma import (
    build_luma_tools,
    build_luma_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.notion import (
    build_notion_tools,
    build_notion_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.onedrive import (
    build_onedrive_tools,
    build_onedrive_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.connectors.teams import (
    build_teams_tools,
    build_teams_domain_agent,
)
from app.agents.multi_agent_chat.expert_agent.mcp_bridge import build_mcp_route_domain_agent
from app.agents.multi_agent_chat.core.mcp_partition import MCP_ONLY_ROUTE_KEYS_IN_ORDER
from app.agents.multi_agent_chat.routing.domain_routing_spec import DomainRoutingSpec
from app.agents.multi_agent_chat.routing.from_domain_agents import routing_tools_from_specs

_MCP_ONLY_ROUTE_DESCRIPTIONS: dict[str, str] = {
    "linear": (
        "Route Linear work (issues, projects, cycles, documents) via MCP to the Linear sub-agent. "
        "Pass a clear natural-language task."
    ),
    "slack": (
        "Route Slack search and channel/thread reads via MCP to the Slack sub-agent. "
        "Pass a clear natural-language task."
    ),
    "jira": (
        "Route Jira issues and projects via MCP to the Jira sub-agent. "
        "Pass a clear natural-language task."
    ),
    "clickup": (
        "Route ClickUp tasks via MCP to the ClickUp sub-agent. Pass a clear natural-language task."
    ),
    "airtable": (
        "Route Airtable bases and records via MCP to the Airtable sub-agent. "
        "Pass a clear natural-language task."
    ),
    "generic_mcp": (
        "Route user-defined MCP (stdio) server tools to the custom MCP sub-agent. "
        "Pass a clear natural-language task."
    ),
}


def build_supervisor_routing_tools(
    llm: BaseChatModel,
    *,
    registry_dependencies: dict[str, Any] | None = None,
    gmail_curated_context: Callable[[str], str | None] | None = None,
    calendar_curated_context: Callable[[str], str | None] | None = None,
    include_deliverables: bool = True,
    mcp_tools_by_route: dict[str, list[BaseTool]] | None = None,
) -> list[BaseTool]:
    """``expert_agent.builtins`` (research, memory, deliverables) plus ``expert_agent.connectors`` → routing tools.

    Pass ``registry_dependencies`` from
    :func:`app.agents.multi_agent_chat.core.registry.build_registry_dependencies`
    to enable **all** registry-backed routes (Gmail, Calendar, chat, doc stores, Luma, …) and builtins
    (**research**, **memory**, **deliverables** when ``include_deliverables``). Use a real chat ``thread_id``
    in deps when deliverables need thread-scoped registry factories.

    ``mcp_tools_by_route`` maps supervisor route keys (e.g. ``gmail``, ``linear``) to MCP tools loaded
    elsewhere; those tools are merged into the matching expert subgraph only — the supervisor sees
    routing tools, not raw MCP tools.
    """
    mcp = mcp_tools_by_route or {}
    if registry_dependencies is not None:
        gmail_native = build_gmail_tools(registry_dependencies)
        calendar_native = build_calendar_tools(registry_dependencies)
    else:
        gmail_native = []
        calendar_native = []

    gmail_domain_agent = build_gmail_domain_agent(llm, gmail_native + mcp.get("gmail", []))
    calendar_domain_agent = build_calendar_domain_agent(
        llm,
        calendar_native + mcp.get("calendar", []),
    )

    specs: list[DomainRoutingSpec] = [
        DomainRoutingSpec(
            tool_name="gmail",
            description=(
                "Route Gmail-related work to the Gmail sub-agent. "
                "Pass a clear natural-language task."
            ),
            domain_agent=gmail_domain_agent,
            curated_context=gmail_curated_context,
        ),
        DomainRoutingSpec(
            tool_name="calendar",
            description=(
                "Route Google Calendar work to the Calendar sub-agent. "
                "Pass a clear natural-language task."
            ),
            domain_agent=calendar_domain_agent,
            curated_context=calendar_curated_context,
        ),
    ]

    if registry_dependencies is not None:
        research_tools = build_research_tools(registry_dependencies)
        research_agent = build_research_domain_agent(llm, research_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="research",
                description=(
                    "Route web search, page scraping, and SurfSense documentation help to the "
                    "research sub-agent. Pass a clear natural-language task."
                ),
                domain_agent=research_agent,
            ),
        )

        memory_tools = build_memory_tools(registry_dependencies)
        memory_agent = build_memory_domain_agent(llm, memory_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="memory",
                description=(
                    "Route saving long-term facts and preferences (personal or team memory) to the "
                    "memory sub-agent. Pass a clear natural-language task."
                ),
                domain_agent=memory_agent,
            ),
        )

        if include_deliverables:
            deliverables_tools = build_deliverables_tools(registry_dependencies)
            deliverables_agent = build_deliverables_domain_agent(llm, deliverables_tools)
            specs.append(
                DomainRoutingSpec(
                    tool_name="deliverables",
                    description=(
                        "Route structured outputs (reports, podcasts, video presentations, resumes, "
                        "images) to the deliverables sub-agent. Pass a clear natural-language task."
                    ),
                    domain_agent=deliverables_agent,
                ),
            )

        discord_tools = build_discord_tools(registry_dependencies)
        discord_agent = build_discord_domain_agent(
            llm,
            discord_tools + mcp.get("discord", []),
        )
        specs.append(
            DomainRoutingSpec(
                tool_name="discord",
                description=(
                    "Route Discord work (channels, messages) to the Discord sub-agent. "
                    "Pass a clear natural-language task."
                ),
                domain_agent=discord_agent,
            ),
        )

        teams_tools = build_teams_tools(registry_dependencies)
        teams_agent = build_teams_domain_agent(
            llm,
            teams_tools + mcp.get("teams", []),
        )
        specs.append(
            DomainRoutingSpec(
                tool_name="teams",
                description=(
                    "Route Microsoft Teams work (channels, messages) to the Teams sub-agent. "
                    "Pass a clear natural-language task."
                ),
                domain_agent=teams_agent,
            ),
        )

        notion_tools = build_notion_tools(registry_dependencies)
        notion_agent = build_notion_domain_agent(llm, notion_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="notion",
                description=(
                    "Route Notion page work to the Notion sub-agent. Pass a clear natural-language task."
                ),
                domain_agent=notion_agent,
            ),
        )

        confluence_tools = build_confluence_tools(registry_dependencies)
        confluence_agent = build_confluence_domain_agent(llm, confluence_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="confluence",
                description=(
                    "Route Confluence page work to the Confluence sub-agent. "
                    "Pass a clear natural-language task."
                ),
                domain_agent=confluence_agent,
            ),
        )

        google_drive_tools = build_google_drive_tools(registry_dependencies)
        google_drive_agent = build_google_drive_domain_agent(llm, google_drive_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="google_drive",
                description=(
                    "Route Google Drive file work to the Google Drive sub-agent. "
                    "Pass a clear natural-language task."
                ),
                domain_agent=google_drive_agent,
            ),
        )

        dropbox_tools = build_dropbox_tools(registry_dependencies)
        dropbox_agent = build_dropbox_domain_agent(llm, dropbox_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="dropbox",
                description=(
                    "Route Dropbox file work to the Dropbox sub-agent. Pass a clear natural-language task."
                ),
                domain_agent=dropbox_agent,
            ),
        )

        onedrive_tools = build_onedrive_tools(registry_dependencies)
        onedrive_agent = build_onedrive_domain_agent(llm, onedrive_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="onedrive",
                description=(
                    "Route Microsoft OneDrive file work to the OneDrive sub-agent. "
                    "Pass a clear natural-language task."
                ),
                domain_agent=onedrive_agent,
            ),
        )

        luma_tools = build_luma_tools(registry_dependencies)
        luma_agent = build_luma_domain_agent(llm, luma_tools + mcp.get("luma", []))
        specs.append(
            DomainRoutingSpec(
                tool_name="luma",
                description=(
                    "Route Luma calendar events (list, read, create) to the Luma sub-agent. "
                    "Pass a clear natural-language task."
                ),
                domain_agent=luma_agent,
            ),
        )

        for route_key in MCP_ONLY_ROUTE_KEYS_IN_ORDER:
            only_mcp = mcp.get(route_key) or []
            if not only_mcp:
                continue
            desc = _MCP_ONLY_ROUTE_DESCRIPTIONS.get(
                route_key,
                f"Route {route_key} MCP work to the {route_key} sub-agent. Pass a clear natural-language task.",
            )
            specs.append(
                DomainRoutingSpec(
                    tool_name=route_key,
                    description=desc,
                    domain_agent=build_mcp_route_domain_agent(llm, route_key, only_mcp),
                ),
            )

    return routing_tools_from_specs(specs)
