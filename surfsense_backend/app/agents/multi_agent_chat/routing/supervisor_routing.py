"""Compose domain agents + tool lists into supervisor routing tools (one ``@tool`` per category)."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.db import ChatVisibility
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
from app.agents.multi_agent_chat.routing.route_connector_gate import include_connector_route

_MCP_ONLY_ROUTE_DESCRIPTIONS: dict[str, str] = {
    "linear": (
        "Use for Linear issue/project work: find/create issues, update status/assignees, review project progress, and inspect cycles."
    ),
    "slack": (
        "Use for Slack channel communication: read channel/thread history, summarize conversations, and post replies."
    ),
    "jira": (
        "Use for Jira issue/project workflows: search issues, inspect fields, update tickets, and move work through workflow states."
    ),
    "clickup": (
        "Use for ClickUp task management: find tasks/lists, update task fields, and track execution progress."
    ),
    "airtable": (
        "Use for Airtable structured data operations: locate bases/tables and create/read/update records."
    ),
    # generic_mcp intentionally disabled for now.
    # "generic_mcp": (
    #     "Use as a fallback for custom connected app tasks not covered by a named specialist. "
    #     "Do not use if another specialist clearly matches."
    # ),
}


def _memory_route_description(thread_visibility: ChatVisibility | None) -> str:
    if thread_visibility == ChatVisibility.SEARCH_SPACE:
        return "Use for storing durable team memory: shared team preferences, conventions, and long-lived team facts."
    return "Use for storing durable user memory: personal preferences, instructions, and long-lived user facts."


def build_supervisor_routing_tools(
    llm: BaseChatModel,
    *,
    registry_dependencies: dict[str, Any] | None = None,
    include_deliverables: bool = True,
    mcp_tools_by_route: dict[str, list[BaseTool]] | None = None,
    available_connectors: list[str] | None = None,
    thread_visibility: ChatVisibility | None = None,
) -> list[BaseTool]:
    """Build supervisor routing tools: builtins first, then connector experts (same pattern for all).

    Requires ``registry_dependencies`` to produce any routing tools; otherwise returns an empty list.

    Pass ``registry_dependencies`` from
    :func:`app.agents.multi_agent_chat.core.registry.build_registry_dependencies`
    for builtins (**research**, **memory**, **deliverables** when ``include_deliverables``) and every
    registry-backed connector route.

    ``mcp_tools_by_route`` maps route keys to MCP tools merged into the matching expert subgraph.

    When ``available_connectors`` is set (searchable connector strings, same shape as the main chat agent),
    a connector-backed route is registered only if its required searchable connector type is available.
    """
    if registry_dependencies is None:
        return routing_tools_from_specs([])

    mcp = mcp_tools_by_route or {}
    specs: list[DomainRoutingSpec] = []

    research_tools = build_research_tools(registry_dependencies)
    research_agent = build_research_domain_agent(llm, research_tools)
    specs.append(
        DomainRoutingSpec(
            tool_name="research",
            description=(
                "Use for external research: find sources on the web, extract evidence, and answer documentation questions."
            ),
            domain_agent=research_agent,
        ),
    )

    memory_tools = build_memory_tools(registry_dependencies)
    memory_agent = build_memory_domain_agent(
        llm,
        memory_tools,
        thread_visibility=thread_visibility,
    )
    specs.append(
        DomainRoutingSpec(
            tool_name="memory",
            description=_memory_route_description(thread_visibility),
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
                    "Use for deliverables and shareable artifacts: generated reports, podcasts, "
                    "video presentations, resumes, and images—not for routine lookups or single small edits elsewhere."
                ),
                domain_agent=deliverables_agent,
            ),
        )

    # Connector experts (registry-backed + optional MCP merge): alphabetical by route key.
    if include_connector_route("calendar", available_connectors):
        calendar_agent = build_calendar_domain_agent(
            llm,
            build_calendar_tools(registry_dependencies) + mcp.get("calendar", []),
        )
        specs.append(
            DomainRoutingSpec(
                tool_name="calendar",
                description=(
                    "Use for calendar planning and scheduling: check availability, read event details, create events, and update events."
                ),
                domain_agent=calendar_agent,
            ),
        )

    if include_connector_route("confluence", available_connectors):
        confluence_tools = build_confluence_tools(registry_dependencies)
        confluence_agent = build_confluence_domain_agent(llm, confluence_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="confluence",
                description=(
                    "Use for Confluence knowledge pages: search/read existing pages, create new pages, and update page content."
                ),
                domain_agent=confluence_agent,
            ),
        )

    if include_connector_route("discord", available_connectors):
        discord_tools = build_discord_tools(registry_dependencies)
        discord_agent = build_discord_domain_agent(llm, discord_tools + mcp.get("discord", []))
        specs.append(
            DomainRoutingSpec(
                tool_name="discord",
                description=(
                    "Use for Discord communication: read channel/thread messages, gather context, and send replies."
                ),
                domain_agent=discord_agent,
            ),
        )

    if include_connector_route("dropbox", available_connectors):
        dropbox_tools = build_dropbox_tools(registry_dependencies)
        dropbox_agent = build_dropbox_domain_agent(llm, dropbox_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="dropbox",
                description=(
                    "Use for Dropbox file storage tasks: browse folders, read files, and manage Dropbox file content."
                ),
                domain_agent=dropbox_agent,
            ),
        )

    if include_connector_route("gmail", available_connectors):
        gmail_agent = build_gmail_domain_agent(
            llm,
            build_gmail_tools(registry_dependencies) + mcp.get("gmail", []),
        )
        specs.append(
            DomainRoutingSpec(
                tool_name="gmail",
                description=(
                    "Use for Gmail inbox actions: search/read emails, draft or update replies, send messages, and trash emails."
                ),
                domain_agent=gmail_agent,
            ),
        )

    if include_connector_route("google_drive", available_connectors):
        google_drive_tools = build_google_drive_tools(registry_dependencies)
        google_drive_agent = build_google_drive_domain_agent(llm, google_drive_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="google_drive",
                description=(
                    "Use for Google Drive document/file tasks: locate files, inspect content, and manage Drive files or folders."
                ),
                domain_agent=google_drive_agent,
            ),
        )

    if include_connector_route("luma", available_connectors):
        luma_tools = build_luma_tools(registry_dependencies)
        luma_agent = build_luma_domain_agent(llm, luma_tools + mcp.get("luma", []))
        specs.append(
            DomainRoutingSpec(
                tool_name="luma",
                description=(
                    "Use for Luma event operations: list events, inspect event details, and create new events."
                ),
                domain_agent=luma_agent,
            ),
        )

    if include_connector_route("notion", available_connectors):
        notion_tools = build_notion_tools(registry_dependencies)
        notion_agent = build_notion_domain_agent(llm, notion_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="notion",
                description=(
                    "Use for Notion workspace pages: create pages, update page content, and delete pages."
                ),
                domain_agent=notion_agent,
            ),
        )

    if include_connector_route("onedrive", available_connectors):
        onedrive_tools = build_onedrive_tools(registry_dependencies)
        onedrive_agent = build_onedrive_domain_agent(llm, onedrive_tools)
        specs.append(
            DomainRoutingSpec(
                tool_name="onedrive",
                description=(
                    "Use for OneDrive file storage tasks: browse folders, read files, and manage OneDrive file content."
                ),
                domain_agent=onedrive_agent,
            ),
        )

    if include_connector_route("teams", available_connectors):
        teams_tools = build_teams_tools(registry_dependencies)
        teams_agent = build_teams_domain_agent(llm, teams_tools + mcp.get("teams", []))
        specs.append(
            DomainRoutingSpec(
                tool_name="teams",
                description=(
                    "Use for Microsoft Teams communication: read channel/thread messages, gather context, and post replies."
                ),
                domain_agent=teams_agent,
            ),
        )

    for route_key in MCP_ONLY_ROUTE_KEYS_IN_ORDER:
        only_mcp = mcp.get(route_key) or []
        if not only_mcp:
            continue
        if not include_connector_route(route_key, available_connectors):
            continue
        desc = _MCP_ONLY_ROUTE_DESCRIPTIONS.get(
            route_key,
            f"Use for {route_key} tasks related to that system's core work objects and workflows.",
        )
        specs.append(
            DomainRoutingSpec(
                tool_name=route_key,
                description=desc,
                domain_agent=build_mcp_route_domain_agent(llm, route_key, only_mcp),
            ),
        )

    return routing_tools_from_specs(specs)
