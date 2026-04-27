"""
SurfSense deep agent implementation.

This module provides the factory function for creating SurfSense deep agents
with configurable tools via the tools registry and configurable prompts
via NewLLMConfig.

We use ``create_agent`` (from langchain) rather than ``create_deep_agent``
(from deepagents) so that the middleware stack is fully under our control.
This lets us swap in ``SurfSenseFilesystemMiddleware`` — a customisable
subclass of the default ``FilesystemMiddleware`` — while preserving every
other behaviour that ``create_deep_agent`` provides (todo-list, subagents,
summarisation, prompt-caching, etc.).
"""

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent, SubAgentMiddleware, __version__ as deepagents_version
from deepagents.backends import StateBackend
from deepagents.graph import BASE_AGENT_PROMPT
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from langchain.agents import create_agent
from langchain.agents.middleware import TodoListMiddleware
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.middleware import (
    DedupHITLToolCallsMiddleware,
    FileIntentMiddleware,
    KnowledgeBaseSearchMiddleware,
    MemoryInjectionMiddleware,
    SurfSenseFilesystemMiddleware,
)
from app.agents.new_chat.middleware.safe_summarization import (
    create_safe_summarization_middleware,
)
from app.agents.new_chat.system_prompt import (
    build_configurable_system_prompt,
    build_surfsense_system_prompt,
)
from app.agents.new_chat.tools.registry import (
    build_tools_async,
    get_connector_gated_tools,
)
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()

# =============================================================================
# Connector Type Mapping
# =============================================================================

# Maps SearchSourceConnectorType enum values to the searchable document/connector types
# used by pre-search middleware and web_search.
# Live search connectors (TAVILY_API, LINKUP_API, BAIDU_SEARCH_API) are routed to
# the web_search tool; all others are considered local/indexed data.
_CONNECTOR_TYPE_TO_SEARCHABLE: dict[str, str] = {
    # Live search connectors (handled by web_search tool)
    "TAVILY_API": "TAVILY_API",
    "LINKUP_API": "LINKUP_API",
    "BAIDU_SEARCH_API": "BAIDU_SEARCH_API",
    # Local/indexed connectors (handled by KB pre-search middleware)
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
    "DROPBOX_CONNECTOR": "DROPBOX_FILE",  # Connector type differs from document type
    "ONEDRIVE_CONNECTOR": "ONEDRIVE_FILE",  # Connector type differs from document type
    # Composio connectors (unified to native document types).
    # Reverse of NATIVE_TO_LEGACY_DOCTYPE in app.db.
    "COMPOSIO_GOOGLE_DRIVE_CONNECTOR": "GOOGLE_DRIVE_FILE",
    "COMPOSIO_GMAIL_CONNECTOR": "GOOGLE_GMAIL_CONNECTOR",
    "COMPOSIO_GOOGLE_CALENDAR_CONNECTOR": "GOOGLE_CALENDAR_CONNECTOR",
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
    mentioned_document_ids: list[int] | None = None,
    anon_session_id: str | None = None,
    filesystem_selection: FilesystemSelection | None = None,
):
    """
    Create a SurfSense deep agent with configurable tools and prompts.

    The agent comes with built-in tools that can be configured:
    - generate_podcast: Generate audio podcasts from content
    - generate_image: Generate images from text descriptions using AI models
    - scrape_webpage: Extract content from webpages
    - update_memory: Update the user's personal or team memory document

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
            enabled_tools=["scrape_webpage"]
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
    filesystem_selection = filesystem_selection or FilesystemSelection()
    backend_resolver = build_backend_resolver(filesystem_selection)

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

    # Extract the model's context window so tools can size their output.
    _model_profile = getattr(llm, "profile", None)
    _max_input_tokens: int | None = (
        _model_profile.get("max_input_tokens")
        if isinstance(_model_profile, dict)
        else None
    )

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
        "max_input_tokens": _max_input_tokens,
        "llm": llm,
    }

    modified_disabled_tools = list(disabled_tools) if disabled_tools else []
    modified_disabled_tools.extend(get_connector_gated_tools(available_connectors))

    # Remove direct KB search tool; we now pre-seed a scoped filesystem via middleware.
    if "search_knowledge_base" not in modified_disabled_tools:
        modified_disabled_tools.append("search_knowledge_base")

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

    # Build system prompt based on agent_config, scoped to the tools actually enabled
    _t0 = time.perf_counter()
    _enabled_tool_names = {t.name for t in tools}
    _user_disabled_tool_names = set(disabled_tools) if disabled_tools else set()

    # Collect generic MCP connector info so the system prompt can route queries
    # to their tools instead of falling back to "not in knowledge base".
    _mcp_connector_tools: dict[str, list[str]] = {}
    for t in tools:
        meta = getattr(t, "metadata", None) or {}
        if meta.get("mcp_is_generic") and meta.get("mcp_connector_name"):
            _mcp_connector_tools.setdefault(
                meta["mcp_connector_name"],
                [],
            ).append(t.name)

    if _mcp_connector_tools:
        _perf_log.info("MCP connector tool routing: %s", _mcp_connector_tools)

    if agent_config is not None:
        system_prompt = build_configurable_system_prompt(
            custom_system_instructions=agent_config.system_instructions,
            use_default_system_instructions=agent_config.use_default_system_instructions,
            citations_enabled=agent_config.citations_enabled,
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            mcp_connector_tools=_mcp_connector_tools,
        )
    else:
        system_prompt = build_surfsense_system_prompt(
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            mcp_connector_tools=_mcp_connector_tools,
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    # -- Build the middleware stack (mirrors create_deep_agent internals) ------
    _memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    # General-purpose subagent middleware
    gp_middleware = [
        TodoListMiddleware(),
        _memory_middleware,
        FileIntentMiddleware(llm=llm),
        SurfSenseFilesystemMiddleware(
            backend=backend_resolver,
            filesystem_mode=filesystem_selection.mode,
            search_space_id=search_space_id,
            created_by_id=user_id,
            thread_id=thread_id,
        ),
        create_safe_summarization_middleware(llm, StateBackend),
        PatchToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    general_purpose_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": llm,
        "tools": tools,
        "middleware": gp_middleware,
    }

    # Main agent middleware
    deepagent_middleware = [
        TodoListMiddleware(),
        _memory_middleware,
        FileIntentMiddleware(llm=llm),
        KnowledgeBaseSearchMiddleware(
            llm=llm,
            search_space_id=search_space_id,
            filesystem_mode=filesystem_selection.mode,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
            anon_session_id=anon_session_id,
        ),
        SurfSenseFilesystemMiddleware(
            backend=backend_resolver,
            filesystem_mode=filesystem_selection.mode,
            search_space_id=search_space_id,
            created_by_id=user_id,
            thread_id=thread_id,
        ),
        SubAgentMiddleware(backend=StateBackend, subagents=[general_purpose_spec]),
        create_safe_summarization_middleware(llm, StateBackend),
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=tools),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    # Combine system_prompt with BASE_AGENT_PROMPT (same as create_deep_agent)
    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    _t0 = time.perf_counter()
    agent = await asyncio.to_thread(
        create_agent,
        llm,
        system_prompt=final_system_prompt,
        tools=tools,
        middleware=deepagent_middleware,
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
    )
    agent = agent.with_config(
        {
            "recursion_limit": 10_000,
            "metadata": {
                "ls_integration": "deepagents",
                "versions": {"deepagents": deepagents_version},
            },
        }
    )
    _perf_log.info(
        "[create_agent] Graph compiled (create_agent) in %.3fs",
        time.perf_counter() - _t0,
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent
