"""
SurfSense deep agent implementation.

This module provides the factory function for creating SurfSense deep agents
with configurable tools via the tools registry and configurable prompts
via NewLLMConfig.
"""

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends.protocol import SandboxBackendProtocol
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.system_prompt import (
    build_configurable_system_prompt,
    build_surfsense_system_prompt,
)
from app.agents.new_chat.tools.registry import build_tools_async
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService

_perf_log = logging.getLogger("surfsense.perf")

# =============================================================================
# Connector Type Mapping
# =============================================================================

# Maps SearchSourceConnectorType enum values to the searchable document/connector types
# used by the knowledge_base tool. Some connectors map to different document types.
_CONNECTOR_TYPE_TO_SEARCHABLE: dict[str, str] = {
    # Direct mappings (connector type == searchable type)
    "TAVILY_API": "TAVILY_API",
    "SEARXNG_API": "SEARXNG_API",
    "LINKUP_API": "LINKUP_API",
    "BAIDU_SEARCH_API": "BAIDU_SEARCH_API",
    "SLACK_CONNECTOR": "SLACK_CONNECTOR",
    "TEAMS_CONNECTOR": "TEAMS_CONNECTOR",
    "NOTION_CONNECTOR": "NOTION_CONNECTOR",
    "GITHUB_CONNECTOR": "GITHUB_CONNECTOR",
    "LINEAR_CONNECTOR": "LINEAR_CONNECTOR",
    "DISCORD_CONNECTOR": "DISCORD_CONNECTOR",
    "JIRA_CONNECTOR": "JIRA_CONNECTOR",
    "CONFLUENCE_CONNECTOR": "CONFLUENCE_CONNECTOR",
    "CLICKUP_CONNECTOR": "CLICKUP_CONNECTOR",
    "GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
    "GOOGLE_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",  # Connector type differs from document type
    "AIRTABLE_CONNECTOR": "AIRTABLE_CONNECTOR",
    "LUMA_CONNECTOR": "LUMA_CONNECTOR",
    "ELASTICSEARCH_CONNECTOR": "ELASTICSEARCH_CONNECTOR",
    "WEBCRAWLER_CONNECTOR": "CRAWLED_URL",  # Maps to document type
    "BOOKSTACK_CONNECTOR": "BOOKSTACK_CONNECTOR",
    "CIRCLEBACK_CONNECTOR": "CIRCLEBACK",  # Connector type differs from document type
    "OBSIDIAN_CONNECTOR": "OBSIDIAN_CONNECTOR",
    # Composio connectors
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "COMPOSIO_GOOGLE_DRIVE_CONNECTOR",
    "COMPOSIO_GMAIL_CONNECTOR": "COMPOSIO_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR",
}

# Document types that don't come from SearchSourceConnector but should always be searchable
_ALWAYS_AVAILABLE_DOC_TYPES: list[str] = [
    "EXTENSION",  # Browser extension data
    "FILE",  # Uploaded files
    "NOTE",  # User notes
    "YOUTUBE_VIDEO",  # YouTube videos
]


def _map_connectors_to_searchable_types(
    connector_types: list[Any],
) -> list[str]:
    """
    Map SearchSourceConnectorType enums to searchable document/connector types.

    This function:
    1. Converts connector type enums to their searchable counterparts
    2. Includes always-available document types (EXTENSION, FILE, NOTE, YOUTUBE_VIDEO)
    3. Deduplicates while preserving order

    Args:
        connector_types: List of SearchSourceConnectorType enum values

    Returns:
        List of searchable connector/document type strings
    """
    result_set: set[str] = set()
    result_list: list[str] = []

    # Add always-available document types first
    for doc_type in _ALWAYS_AVAILABLE_DOC_TYPES:
        if doc_type not in result_set:
            result_set.add(doc_type)
            result_list.append(doc_type)

    # Map each connector type to its searchable equivalent
    for ct in connector_types:
        # Handle both enum and string types
        ct_str = ct.value if hasattr(ct, "value") else str(ct)
        searchable = _CONNECTOR_TYPE_TO_SEARCHABLE.get(ct_str)
        if searchable and searchable not in result_set:
            result_set.add(searchable)
            result_list.append(searchable)

    return result_list


# =============================================================================
# Deep Agent Factory
# =============================================================================


async def create_surfsense_deep_agent(
    llm: BaseChatModel,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    checkpointer: Checkpointer,
    user_id: str | None = None,
    thread_id: int | None = None,
    agent_config: AgentConfig | None = None,
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
    firecrawl_api_key: str | None = None,
    thread_visibility: ChatVisibility | None = None,
    sandbox_backend: SandboxBackendProtocol | None = None,
):
    """
    Create a SurfSense deep agent with configurable tools and prompts.

    The agent comes with built-in tools that can be configured:
    - search_knowledge_base: Search the user's personal knowledge base
    - generate_podcast: Generate audio podcasts from content
    - generate_image: Generate images from text descriptions using AI models
    - link_preview: Fetch rich previews for URLs
    - display_image: Display images in chat
    - scrape_webpage: Extract content from webpages
    - save_memory: Store facts/preferences about the user
    - recall_memory: Retrieve relevant user memories

    The agent also includes TodoListMiddleware by default (via create_deep_agent) which provides:
    - write_todos: Create and update planning/todo lists for complex tasks

    The system prompt can be configured via agent_config:
    - Custom system instructions (or use defaults)
    - Citation toggle (enable/disable citation requirements)

    Args:
        llm: ChatLiteLLM instance for the agent's language model
        search_space_id: The user's search space ID
        db_session: Database session for tools that need DB access
        connector_service: Initialized connector service for knowledge base search
        checkpointer: LangGraph checkpointer for conversation state persistence.
                      Use AsyncPostgresSaver for production or MemorySaver for testing.
        user_id: The current user's UUID string (required for memory tools)
        agent_config: Optional AgentConfig from NewLLMConfig for prompt configuration.
                     If None, uses default system prompt with citations enabled.
        enabled_tools: Explicit list of tool names to enable. If None, all default tools
                      are enabled. Use this to limit which tools are available.
        disabled_tools: List of tool names to disable. Applied after enabled_tools.
                       Use this to exclude specific tools from the defaults.
        additional_tools: Extra custom tools to add beyond the built-in ones.
                         These are always added regardless of enabled/disabled settings.
        firecrawl_api_key: Optional Firecrawl API key for premium web scraping.
                          Falls back to Chromium/Trafilatura if not provided.
        sandbox_backend: Optional sandbox backend (e.g. DaytonaSandbox) for
                        secure code execution. When provided, the agent gets an
                        isolated ``execute`` tool for running shell commands.

    Returns:
        CompiledStateGraph: The configured deep agent

    Examples:
        # Create agent with all default tools and default prompt
        agent = create_surfsense_deep_agent(llm, search_space_id, db_session, ...)

        # Create agent with custom prompt configuration
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            agent_config=AgentConfig(
                provider="OPENAI",
                model_name="gpt-4",
                api_key="...",
                system_instructions="Custom instructions...",
                citations_enabled=False,
            )
        )

        # Create agent with only specific tools
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            enabled_tools=["search_knowledge_base", "link_preview"]
        )

        # Create agent without podcast generation
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            disabled_tools=["generate_podcast"]
        )

        # Add custom tools
        agent = create_surfsense_deep_agent(
            llm, search_space_id, db_session, ...,
            additional_tools=[my_custom_tool]
        )
    """
    _t_agent_total = time.perf_counter()

    # Discover available connectors and document types for this search space
    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        connector_types = await connector_service.get_available_connectors(
            search_space_id
        )
        if connector_types:
            available_connectors = _map_connectors_to_searchable_types(connector_types)

        available_document_types = await connector_service.get_available_document_types(
            search_space_id
        )
    except Exception as e:
        logging.warning(f"Failed to discover available connectors/document types: {e}")
    _perf_log.info(
        "[create_agent] Connector/doc-type discovery in %.3fs",
        time.perf_counter() - _t0,
    )

    # Build dependencies dict for the tools registry
    visibility = thread_visibility or ChatVisibility.PRIVATE
    dependencies = {
        "search_space_id": search_space_id,
        "db_session": db_session,
        "connector_service": connector_service,
        "firecrawl_api_key": firecrawl_api_key,
        "user_id": user_id,
        "thread_id": thread_id,
        "thread_visibility": visibility,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
    }

    # Disable Notion action tools if no Notion connector is configured
    modified_disabled_tools = list(disabled_tools) if disabled_tools else []
    has_notion_connector = (
        available_connectors is not None and "NOTION_CONNECTOR" in available_connectors
    )
    if not has_notion_connector:
        notion_tools = [
            "create_notion_page",
            "update_notion_page",
            "delete_notion_page",
        ]
        modified_disabled_tools.extend(notion_tools)

    # Disable Linear action tools if no Linear connector is configured
    has_linear_connector = (
        available_connectors is not None and "LINEAR_CONNECTOR" in available_connectors
    )
    if not has_linear_connector:
        linear_tools = [
            "create_linear_issue",
            "update_linear_issue",
            "delete_linear_issue",
        ]
        modified_disabled_tools.extend(linear_tools)

    # Build tools using the async registry (includes MCP tools)
    _t0 = time.perf_counter()
    tools = await build_tools_async(
        dependencies=dependencies,
        enabled_tools=enabled_tools,
        disabled_tools=modified_disabled_tools,
        additional_tools=list(additional_tools) if additional_tools else None,
    )
    _perf_log.info(
        "[create_agent] build_tools_async in %.3fs (%d tools)",
        time.perf_counter() - _t0,
        len(tools),
    )

    # Build system prompt based on agent_config
    _t0 = time.perf_counter()
    _sandbox_enabled = sandbox_backend is not None
    if agent_config is not None:
        system_prompt = build_configurable_system_prompt(
            custom_system_instructions=agent_config.system_instructions,
            use_default_system_instructions=agent_config.use_default_system_instructions,
            citations_enabled=agent_config.citations_enabled,
            thread_visibility=thread_visibility,
            sandbox_enabled=_sandbox_enabled,
        )
    else:
        system_prompt = build_surfsense_system_prompt(
            thread_visibility=thread_visibility,
            sandbox_enabled=_sandbox_enabled,
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    # Build optional kwargs for the deep agent
    deep_agent_kwargs: dict[str, Any] = {}
    if sandbox_backend is not None:
        deep_agent_kwargs["backend"] = sandbox_backend

    _t0 = time.perf_counter()
    agent = await asyncio.to_thread(
        create_deep_agent,
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
        **deep_agent_kwargs,
    )
    _perf_log.info(
        "[create_agent] Graph compiled (create_deep_agent) in %.3fs",
        time.perf_counter() - _t0,
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent
