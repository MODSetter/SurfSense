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
summarisation, etc.). Prompt caching is configured at LLM-build time via
``apply_litellm_prompt_caching`` (LiteLLM-native, multi-provider) rather
than as a middleware.
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
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
from langchain.agents import create_agent
from langchain.agents.middleware import (
    LLMToolSelectorMiddleware,
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.agent_cache import (
    flags_signature,
    get_cache,
    stable_hash,
    system_prompt_hash,
    tools_signature,
)
from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.feature_flags import AgentFeatureFlags, get_flags
from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.new_chat.llm_config import AgentConfig
from app.agents.new_chat.middleware import (
    ActionLogMiddleware,
    AnonymousDocumentMiddleware,
    BusyMutexMiddleware,
    ClearToolUsesEdit,
    DedupHITLToolCallsMiddleware,
    DoomLoopMiddleware,
    FileIntentMiddleware,
    FlattenSystemMessageMiddleware,
    KnowledgeBasePersistenceMiddleware,
    KnowledgePriorityMiddleware,
    KnowledgeTreeMiddleware,
    MemoryInjectionMiddleware,
    NoopInjectionMiddleware,
    OtelSpanMiddleware,
    PermissionMiddleware,
    RetryAfterMiddleware,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
    SurfSenseFilesystemMiddleware,
    ToolCallNameRepairMiddleware,
    build_skills_backend_factory,
    create_surfsense_compaction_middleware,
    default_skills_sources,
)
from app.agents.new_chat.permissions import Rule, Ruleset
from app.agents.new_chat.plugin_loader import (
    PluginContext,
    load_allowed_plugin_names_from_env,
    load_plugin_middlewares,
)
from app.agents.new_chat.prompt_caching import apply_litellm_prompt_caching
from app.agents.new_chat.subagents import build_specialized_subagents
from app.agents.new_chat.system_prompt import (
    build_configurable_system_prompt,
    build_surfsense_system_prompt,
)
from app.agents.new_chat.tools.invalid_tool import (
    INVALID_TOOL_NAME,
    invalid_tool,
)
from app.agents.new_chat.tools.registry import (
    BUILTIN_TOOLS,
    build_tools_async,
    get_connector_gated_tools,
)
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


def _resolve_prompt_model_name(
    agent_config: AgentConfig | None,
    llm: BaseChatModel,
) -> str | None:
    """Resolve the model id to feed to provider-variant detection.

    Preference order (matches the established idiom in
    ``llm_router_service.py`` — see ``params.get("base_model") or
    params.get("model", "")`` usages there):

    1. ``agent_config.litellm_params["base_model"]`` — required for Azure
       deployments where ``model_name`` is the deployment slug, not the
       underlying family. Without this, a deployment named e.g.
       ``"prod-chat-001"`` would silently miss every provider regex.
    2. ``agent_config.model_name`` — the user's configured model id.
    3. ``getattr(llm, "model", None)`` — fallback for direct callers that
       don't supply an ``AgentConfig`` (currently a defensive path; all
       production callers pass ``agent_config``).

    Returns ``None`` when nothing is available; ``compose_system_prompt``
    treats that as the ``"default"`` variant (no provider block emitted).
    """
    if agent_config is not None:
        params = agent_config.litellm_params or {}
        base_model = params.get("base_model")
        if isinstance(base_model, str) and base_model.strip():
            return base_model
        if agent_config.model_name:
            return agent_config.model_name
    return getattr(llm, "model", None)


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

    # Layer thread-aware prompt caching onto the LLM. Idempotent with the
    # build-time call in ``llm_config.py``; this run merely adds
    # ``prompt_cache_key=f"surfsense-thread-{thread_id}"`` for OpenAI-family
    # configs now that ``thread_id`` is known. No-op when ``thread_id`` is
    # None or the provider is non-OpenAI-family.
    apply_litellm_prompt_caching(llm, agent_config=agent_config, thread_id=thread_id)

    filesystem_selection = filesystem_selection or FilesystemSelection()
    backend_resolver = build_backend_resolver(
        filesystem_selection,
        search_space_id=search_space_id
        if filesystem_selection.mode == FilesystemMode.CLOUD
        else None,
    )

    # Discover available connectors and document types for this search space.
    #
    # NOTE: These two calls cannot be parallelized via ``asyncio.gather``.
    # ``ConnectorService`` shares a single ``AsyncSession`` (``self.session``);
    # SQLAlchemy explicitly forbids concurrent operations on the same session
    # ("This session is provisioning a new connection; concurrent operations
    # are not permitted on the same session"). The Phase 1.4 in-process TTL
    # cache in ``connector_service`` already collapses the warm path to a
    # near-zero pair of dict lookups, so sequential awaits cost nothing in
    # the common case while remaining correct on cold cache misses.
    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        try:
            connector_types_result = await connector_service.get_available_connectors(
                search_space_id
            )
            if connector_types_result:
                available_connectors = _map_connectors_to_searchable_types(
                    connector_types_result
                )
        except Exception as e:
            logging.warning("Failed to discover available connectors: %s", e)

        try:
            available_document_types = (
                await connector_service.get_available_document_types(search_space_id)
            )
        except Exception as e:
            logging.warning("Failed to discover available document types: %s", e)
    except Exception as e:  # pragma: no cover - defensive outer guard
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

    # Remove direct KB search tool; KnowledgePriorityMiddleware now runs hybrid
    # search per turn and surfaces hits as a <priority_documents> hint plus
    # `<chunk_index matched="true">` markers inside lazy-loaded XML.
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

    # Register the ``invalid`` tool only when tool-call repair is on. It
    # is dispatched only when :class:`ToolCallNameRepairMiddleware`
    # rewrites a malformed call. We intentionally append it AFTER
    # ``build_tools_async`` so it never appears in the system-prompt
    # tool list (which is built from the registry, not the bound tool
    # list).
    _flags: AgentFeatureFlags = get_flags()
    if _flags.enable_tool_call_repair and INVALID_TOOL_NAME not in {
        t.name for t in tools
    }:
        tools = [*list(tools), invalid_tool]
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
            model_name=_resolve_prompt_model_name(agent_config, llm),
        )
    else:
        system_prompt = build_surfsense_system_prompt(
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            mcp_connector_tools=_mcp_connector_tools,
            model_name=_resolve_prompt_model_name(agent_config, llm),
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    # Combine system_prompt with BASE_AGENT_PROMPT (same as create_deep_agent)
    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    # The middleware stack — and especially ``SubAgentMiddleware`` — is *not*
    # cheap to build. ``SubAgentMiddleware.__init__`` calls ``create_agent``
    # synchronously to compile the general-purpose subagent's full state graph
    # (every tool + every middleware → pydantic schemas + langgraph compile).
    # On gpt-5.x agents that's roughly 1.5-2s of pure CPU work. If we run it
    # directly here it blocks the asyncio event loop for the whole streaming
    # task (and any other coroutine sharing this loop), which is why
    # "agent creation" wall-clock time used to stretch to ~3-4s. Move the
    # entire middleware build + main-graph compile into a single
    # ``asyncio.to_thread`` so the heavy CPU work runs off-loop and the
    # event loop stays responsive.
    #
    # PHASE 1: cache the resulting compiled graph. ``agent_cache`` is keyed
    # on every per-request value that any middleware in the stack closes
    # over in ``__init__`` — drop one and you risk leaking state across
    # threads. Hits collapse this whole block to a microsecond lookup;
    # misses pay the original CPU cost AND populate the cache.
    config_id = agent_config.config_id if agent_config is not None else None

    async def _build_agent() -> Any:
        return await asyncio.to_thread(
            _build_compiled_agent_blocking,
            llm=llm,
            tools=tools,
            final_system_prompt=final_system_prompt,
            backend_resolver=backend_resolver,
            filesystem_mode=filesystem_selection.mode,
            search_space_id=search_space_id,
            user_id=user_id,
            thread_id=thread_id,
            visibility=visibility,
            anon_session_id=anon_session_id,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            # ``mentioned_document_ids`` is consumed by
            # ``KnowledgePriorityMiddleware`` per turn via
            # ``runtime.context`` (Phase 1.5). We still pass the
            # caller-provided list here for the legacy fallback path
            # (cache disabled / context not propagated) — the middleware
            # drains its own copy after the first read so a cached graph
            # never replays stale mentions.
            mentioned_document_ids=mentioned_document_ids,
            max_input_tokens=_max_input_tokens,
            flags=_flags,
            checkpointer=checkpointer,
        )

    _t0 = time.perf_counter()
    if _flags.enable_agent_cache and not _flags.disable_new_agent_stack:
        # Cache key components — order matters only for human readability;
        # the resulting hash is what's stored. Every component must
        # rotate on a real shape change AND stay stable across identical
        # invocations.
        cache_key = stable_hash(
            "v1",  # schema version of the key — bump if components change
            config_id,
            thread_id,
            user_id,
            search_space_id,
            visibility,
            filesystem_selection.mode,
            anon_session_id,
            tools_signature(
                tools,
                available_connectors=available_connectors,
                available_document_types=available_document_types,
            ),
            flags_signature(_flags),
            system_prompt_hash(final_system_prompt),
            _max_input_tokens,
            # ``mentioned_document_ids`` deliberately omitted — middleware
            # reads it from ``runtime.context`` (Phase 1.5).
        )
        agent = await get_cache().get_or_build(cache_key, builder=_build_agent)
    else:
        agent = await _build_agent()
    _perf_log.info(
        "[create_agent] Middleware stack + graph compiled in %.3fs (cache=%s)",
        time.perf_counter() - _t0,
        "on"
        if _flags.enable_agent_cache and not _flags.disable_new_agent_stack
        else "off",
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent


# Tools whose output is too costly / lossy to discard. Keep this
# conservative — anything listed here is *never* pruned by
# :class:`ContextEditingMiddleware`. The list is filtered against
# actually-bound tool names so disabled connectors don't show up here.
_PRUNE_PROTECTED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "generate_report",
        "generate_resume",
        "generate_podcast",
        "generate_video_presentation",
        "generate_image",
        # Read-heavy connector reads — recomputing them is expensive
        "read_email",
        "search_emails",
        # The fallback for malformed tool calls — keep its replies visible
        "invalid",
    }
)


def _safe_exclude_tools(tools: Sequence[BaseTool]) -> tuple[str, ...]:
    """Return ``exclude_tools`` derived from the actually-bound tool list.

    Filters :data:`_PRUNE_PROTECTED_TOOL_NAMES` against the bound tools
    so we never list tools that don't exist (would be a silent no-op).
    """
    enabled = {t.name for t in tools}
    return tuple(name for name in _PRUNE_PROTECTED_TOOL_NAMES if name in enabled)


# Connector gating: any tool whose ``ToolDefinition.required_connector``
# isn't actually wired up gets a synthesized permission deny rule so
# execution attempts short-circuit with ``permission_denied`` instead of
# bubbling up provider-specific 401/404 errors. Mirrors OpenCode's
# ``Permission.disabled`` (declarative, per-tool gating) — replaces the
# legacy binary ``_CONNECTOR_TYPE_TO_SEARCHABLE`` substring-heuristic.
def _synthesize_connector_deny_rules(
    *,
    available_connectors: list[str] | None,
    enabled_tool_names: set[str],
) -> list[Rule]:
    """Build deny rules for tools whose required connector is not enabled.

    Source of truth is ``ToolDefinition.required_connector`` in
    :data:`BUILTIN_TOOLS`. A tool only gets a deny rule when:

    1. It is currently bound (``enabled_tool_names``).
    2. It declares a ``required_connector``.
    3. That connector is *not* in ``available_connectors``.
    """
    available = set(available_connectors or [])
    deny: list[Rule] = []
    for tool_def in BUILTIN_TOOLS:
        if tool_def.name not in enabled_tool_names:
            continue
        rc = tool_def.required_connector
        if rc and rc not in available:
            deny.append(Rule(permission=tool_def.name, pattern="*", action="deny"))
    return deny


def _build_compiled_agent_blocking(
    *,
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    final_system_prompt: str,
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | None,
    visibility: ChatVisibility,
    anon_session_id: str | None,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
    max_input_tokens: int | None,
    flags: AgentFeatureFlags,
    checkpointer: Checkpointer,
):
    """Build the middleware stack and compile the agent graph synchronously.

    Runs in a worker thread (see ``asyncio.to_thread`` call site) so the heavy
    CPU work — most notably ``SubAgentMiddleware.__init__`` eagerly calling
    ``create_agent`` to compile the general-purpose subagent — does not block
    the event loop.
    """
    _memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    # General-purpose subagent middleware
    # Subagent omits AnonymousDocumentMiddleware, KnowledgeTreeMiddleware,
    # KnowledgePriorityMiddleware, and KnowledgeBasePersistenceMiddleware - it
    # inherits state and tools from the parent, but should not (a) re-load
    # anon docs / re-render the tree / re-run hybrid search, or (b) commit at
    # its own completion (only the top-level agent's aafter_agent commits).
    gp_middleware = [
        TodoListMiddleware(),
        _memory_middleware,
        FileIntentMiddleware(llm=llm),
        SurfSenseFilesystemMiddleware(
            backend=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            created_by_id=user_id,
            thread_id=thread_id,
        ),
        create_surfsense_compaction_middleware(llm, StateBackend),
        PatchToolCallsMiddleware(),
    ]

    general_purpose_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": llm,
        "tools": tools,
        "middleware": gp_middleware,
    }

    # Specialized user-facing subagents (explore, report_writer,
    # connector_negotiator). Registered through SubAgentMiddleware alongside
    # the general-purpose spec so the parent's `task` tool can address them
    # by name. Off by default until the flag flips so existing deployments
    # don't see new agent types in the task tool description.
    specialized_subagents: list[SubAgent] = []
    if flags.enable_specialized_subagents and not flags.disable_new_agent_stack:
        try:
            # Specialized subagents share the parent's filesystem +
            # todo view so their system prompts (which promise
            # ``read_file``, ``ls``, ``grep``, ``glob``, ``write_todos``)
            # actually match runtime behavior. Build *fresh* instances
            # rather than aliasing the parent's GP middleware to avoid
            # subtle state coupling across compiled graphs.
            subagent_extra_middleware: list = [
                TodoListMiddleware(),
                SurfSenseFilesystemMiddleware(
                    backend=backend_resolver,
                    filesystem_mode=filesystem_mode,
                    search_space_id=search_space_id,
                    created_by_id=user_id,
                    thread_id=thread_id,
                ),
            ]
            specialized_subagents = build_specialized_subagents(
                tools=tools,
                model=llm,
                extra_middleware=subagent_extra_middleware,
            )
            logging.info(
                "Specialized subagents registered for task tool: %s",
                [s["name"] for s in specialized_subagents],
            )
        except Exception as exc:  # pragma: no cover - defensive
            logging.warning(
                "Specialized subagent build failed; running without them: %s",
                exc,
            )
            specialized_subagents = []

    subagent_specs: list[SubAgent] = [general_purpose_spec, *specialized_subagents]

    # Main agent middleware
    # Order: AnonDoc -> Tree -> Priority -> FileIntent -> Filesystem -> Persistence -> ...
    # before_agent hooks run in declared order; later injections sit closer to
    # the latest human turn. Tree (large + cacheable) is injected earliest so
    # provider-side prefix caching has more material to hit; FileIntent (most
    # actionable per-turn contract) is injected closest to the user message.
    #
    # ``wrap_model_call`` ordering: the FIRST middleware in the list is the
    # OUTERMOST wrapper. To ensure prune executes before summarization,
    # place ``SpillingContextEditingMiddleware`` before
    # ``SurfSenseCompactionMiddleware``. Compaction is the canonical
    # token-budget defense; the Bedrock buffer-empty defense is folded
    # into ``SurfSenseCompactionMiddleware``.
    summarization_mw = create_surfsense_compaction_middleware(llm, StateBackend)
    _ = flags.enable_compaction_v2  # historical flag; retained for telemetry parity

    # ContextEditing prune. Trigger at 55% of ``max_input_tokens``,
    # earlier than summarization (~85%). When disabled, no edit runs.
    context_edit_mw = None
    if (
        flags.enable_context_editing
        and not flags.disable_new_agent_stack
        and max_input_tokens
    ):
        spill_edit = SpillToBackendEdit(
            trigger=int(max_input_tokens * 0.55),
            clear_at_least=int(max_input_tokens * 0.15),
            keep=5,
            exclude_tools=_safe_exclude_tools(tools),
            clear_tool_inputs=True,
        )
        clear_edit = ClearToolUsesEdit(
            trigger=int(max_input_tokens * 0.55),
            clear_at_least=int(max_input_tokens * 0.15),
            keep=5,
            exclude_tools=_safe_exclude_tools(tools),
            clear_tool_inputs=True,
            placeholder="[cleared - older tool output trimmed for context]",
        )
        context_edit_mw = SpillingContextEditingMiddleware(
            edits=[spill_edit, clear_edit],
            backend_resolver=backend_resolver,
        )

    # Resilience knobs: header-aware retry, model fallback, and
    # per-thread / per-run call-count limits. The fallback / limit
    # middlewares are vanilla LangChain primitives; ``RetryAfter`` is
    # SurfSense's header-aware variant (see its module docstring).
    retry_mw = (
        RetryAfterMiddleware(max_retries=3)
        if flags.enable_retry_after and not flags.disable_new_agent_stack
        else None
    )
    # Fallback chain — primary is the agent's own model; we add cheap
    # alternatives. Off by default; only the first call site that
    # configures the chain via env should enable it.
    fallback_mw: ModelFallbackMiddleware | None = None
    if flags.enable_model_fallback and not flags.disable_new_agent_stack:
        try:
            fallback_mw = ModelFallbackMiddleware(
                "openai:gpt-4o-mini",
                "anthropic:claude-3-5-haiku-20241022",
            )
        except Exception:
            logging.warning("ModelFallbackMiddleware init failed; skipping.")
            fallback_mw = None
    model_call_limit_mw = (
        ModelCallLimitMiddleware(
            thread_limit=120,
            run_limit=80,
            exit_behavior="end",
        )
        if flags.enable_model_call_limit and not flags.disable_new_agent_stack
        else None
    )
    tool_call_limit_mw = (
        ToolCallLimitMiddleware(
            thread_limit=300, run_limit=80, exit_behavior="continue"
        )
        if flags.enable_tool_call_limit and not flags.disable_new_agent_stack
        else None
    )

    # Provider-compat ``_noop`` injection (mirrors OpenCode's
    # ``llm.ts`` workaround for providers that reject empty assistant
    # turns or alternating-role constraints).
    noop_mw = (
        NoopInjectionMiddleware()
        if flags.enable_compaction_v2 and not flags.disable_new_agent_stack
        else None
    )

    # Tool-call name repair (lowercase + ``invalid`` fallback).
    #
    # ``registered_tool_names`` MUST cover every tool the model can legitimately
    # call. That includes the bound ``tools`` list AND every tool provided by
    # middleware in the stack — ``FilesystemMiddleware`` (read_file, ls, grep,
    # glob, edit_file, write_file, execute), ``TodoListMiddleware``
    # (write_todos), ``SubAgentMiddleware`` (task), ``SkillsMiddleware`` (skill
    # loaders), etc. If we only inspect ``tools`` here, every call to
    # ``read_file`` / ``ls`` / ``grep`` from the model will be rewritten to
    # ``invalid`` because the repair middleware doesn't recognize them. The
    # built-in deepagents middleware aren't in scope yet at this point of the
    # function but they're added unconditionally below, so we hard-code their
    # canonical names alongside the dynamic ``tools`` set.
    repair_mw = None
    if flags.enable_tool_call_repair and not flags.disable_new_agent_stack:
        registered_names: set[str] = {t.name for t in tools}
        # Tools owned by the standard deepagents middleware stack and the
        # SurfSense filesystem extension.
        registered_names |= {
            "write_todos",
            "ls",
            "read_file",
            "write_file",
            "edit_file",
            "glob",
            "grep",
            "execute",
            "task",
            "mkdir",
            "cd",
            "pwd",
            "move_file",
            "rm",
            "rmdir",
            "list_tree",
            "execute_code",
        }
        repair_mw = ToolCallNameRepairMiddleware(
            registered_tool_names=registered_names,
            # Disable fuzzy matching to avoid silent rewrites; the
            # lowercase + ``invalid`` fallback alone covers >95% of
            # observed model errors.
            fuzzy_match_threshold=None,
        )

    # Doom-loop detector. Off by default until the frontend handles
    # ``permission == "doom_loop"`` interrupts.
    doom_loop_mw = (
        DoomLoopMiddleware(threshold=3)
        if flags.enable_doom_loop and not flags.disable_new_agent_stack
        else None
    )

    # PermissionMiddleware. Layers, earliest -> latest (last match wins,
    # same evaluation order as OpenCode's ``permission/index.ts``):
    #
    # 1. ``surfsense_defaults`` — single ``allow */*`` rule. SurfSense
    #    already runs per-tool HITL (see ``tools/hitl.py``) for mutating
    #    connector tools, so we only want PermissionMiddleware to *deny*
    #    things the user has gated off; the default fallback in
    #    ``permissions.evaluate`` is ``ask``, which would double-prompt
    #    on every safe read-only call (``ls``, ``read_file``, ``grep``,
    #    ``glob``, ``web_search`` …) and, on resume, replay the previous
    #    reject decision into innocent calls.
    # 2. ``desktop_safety`` — ``ask`` for destructive filesystem ops when
    #    the agent is operating against the user's real disk. Cloud mode
    #    has full revision-based revert via ``revert_service``, but
    #    desktop mode hits disk immediately with no undo, so an
    #    accidental ``rm`` / ``rmdir`` / ``move_file`` / ``edit_file`` /
    #    ``write_file`` is unrecoverable. This layer is forced on in
    #    desktop mode regardless of ``enable_permission`` because the
    #    safety net is non-negotiable.
    # 3. ``connector_synthesized`` — deny rules for tools whose required
    #    connector is not connected to this space. Overrides #1/#2.
    # 4. (future) user-defined rules from ``agent_permission_rules`` table
    #    via the Agent Permissions UI. Loaded last so they override all.
    permission_mw: PermissionMiddleware | None = None
    is_desktop_fs = filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER
    permission_enabled = flags.enable_permission and not flags.disable_new_agent_stack
    # Build the middleware whenever it has work to do: either the user
    # opted into the rule engine, OR we're in desktop mode and need the
    # safety rules unconditionally.
    if permission_enabled or is_desktop_fs:
        rulesets: list[Ruleset] = [
            Ruleset(
                rules=[Rule(permission="*", pattern="*", action="allow")],
                origin="surfsense_defaults",
            ),
        ]
        if is_desktop_fs:
            rulesets.append(
                Ruleset(
                    rules=[
                        Rule(permission="rm", pattern="*", action="ask"),
                        Rule(permission="rmdir", pattern="*", action="ask"),
                        Rule(permission="move_file", pattern="*", action="ask"),
                        Rule(permission="edit_file", pattern="*", action="ask"),
                        Rule(permission="write_file", pattern="*", action="ask"),
                    ],
                    origin="desktop_safety",
                )
            )
        if permission_enabled:
            synthesized = _synthesize_connector_deny_rules(
                available_connectors=available_connectors,
                enabled_tool_names={t.name for t in tools},
            )
            rulesets.append(Ruleset(rules=synthesized, origin="connector_synthesized"))
        permission_mw = PermissionMiddleware(rulesets=rulesets)

    # ActionLogMiddleware. Off by default until the ``agent_action_log``
    # table is migrated. When enabled, persists one row per tool call
    # with optional reverse_descriptor for
    # ``POST /api/threads/{thread_id}/revert/{action_id}``. Sits inside
    # ``permission`` so denied calls aren't logged as completions.
    action_log_mw: ActionLogMiddleware | None = None
    if (
        flags.enable_action_log
        and not flags.disable_new_agent_stack
        and thread_id is not None
    ):
        try:
            tool_defs_by_name = {td.name: td for td in BUILTIN_TOOLS}
            action_log_mw = ActionLogMiddleware(
                thread_id=thread_id,
                search_space_id=search_space_id,
                user_id=user_id,
                tool_definitions=tool_defs_by_name,
            )
        except Exception:  # pragma: no cover - defensive
            logging.warning(
                "ActionLogMiddleware init failed; running without it.",
                exc_info=True,
            )
            action_log_mw = None

    # Per-thread busy mutex (refuse a second concurrent turn on the same
    # thread; see :class:`BusyMutexMiddleware` docstring).
    busy_mutex_mw: BusyMutexMiddleware | None = (
        BusyMutexMiddleware()
        if flags.enable_busy_mutex and not flags.disable_new_agent_stack
        else None
    )

    # OpenTelemetry spans (model.call + tool.call). Lives just inside
    # BusyMutex so it spans every retry/fallback attempt of the current
    # turn but never wraps a queued/blocked turn.
    otel_mw: OtelSpanMiddleware | None = (
        OtelSpanMiddleware()
        if flags.enable_otel and not flags.disable_new_agent_stack
        else None
    )

    # Plugin entry-point loader. Off by default; opt-in via the
    # ``SURFSENSE_ENABLE_PLUGIN_LOADER`` flag. The allowlist is read from
    # the ``SURFSENSE_ALLOWED_PLUGINS`` env var (comma-separated). A future
    # PR can wire it through ``global_llm_config.yaml``.
    plugin_middlewares: list[Any] = []
    if flags.enable_plugin_loader and not flags.disable_new_agent_stack:
        try:
            allowed_names = load_allowed_plugin_names_from_env()
            if allowed_names:
                plugin_middlewares = load_plugin_middlewares(
                    PluginContext.build(
                        search_space_id=search_space_id,
                        user_id=user_id,
                        thread_visibility=visibility,
                        llm=llm,
                    ),
                    allowed_plugin_names=allowed_names,
                )
        except Exception:  # pragma: no cover - defensive
            logging.warning(
                "Plugin loader failed; continuing without plugins.",
                exc_info=True,
            )
            plugin_middlewares = []

    # SkillsMiddleware (deepagents) loads built-in + space-authored
    # skills via a CompositeBackend. Sources are layered: built-in first,
    # space last, so a search-space-authored skill of the same name
    # overrides the bundled one.
    skills_mw: SkillsMiddleware | None = None
    if flags.enable_skills and not flags.disable_new_agent_stack:
        try:
            skills_factory = build_skills_backend_factory(
                search_space_id=search_space_id
                if filesystem_mode == FilesystemMode.CLOUD
                else None,
            )
            skills_mw = SkillsMiddleware(
                backend=skills_factory,
                sources=default_skills_sources(),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logging.warning("SkillsMiddleware init failed; skipping: %s", exc)
            skills_mw = None

    # LangChain's LLM-driven tool selection — only enabled for stacks
    # large enough to need narrowing (>30 tools).
    selector_mw: LLMToolSelectorMiddleware | None = None
    if (
        flags.enable_llm_tool_selector
        and not flags.disable_new_agent_stack
        and len(tools) > 30
    ):
        try:
            selector_mw = LLMToolSelectorMiddleware(
                model="openai:gpt-4o-mini",
                max_tools=12,
                always_include=[
                    name
                    for name in (
                        "update_memory",
                        "get_connected_accounts",
                        "scrape_webpage",
                    )
                    if name in {t.name for t in tools}
                ],
            )
        except Exception:
            logging.warning("LLMToolSelectorMiddleware init failed; skipping.")
            selector_mw = None

    deepagent_middleware = [
        # BusyMutex is OUTERMOST: it must wrap the entire stream so no
        # other turn can sneak in while this one is mid-flight.
        busy_mutex_mw,
        # OTel spans sit just inside BusyMutex so each retry attempt
        # gets its own model.call / tool.call span.
        otel_mw,
        TodoListMiddleware(),
        _memory_middleware,
        AnonymousDocumentMiddleware(
            anon_session_id=anon_session_id,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        KnowledgeTreeMiddleware(
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            llm=llm,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        KnowledgePriorityMiddleware(
            llm=llm,
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
        ),
        FileIntentMiddleware(llm=llm),
        SurfSenseFilesystemMiddleware(
            backend=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            created_by_id=user_id,
            thread_id=thread_id,
        ),
        KnowledgeBasePersistenceMiddleware(
            search_space_id=search_space_id,
            created_by_id=user_id,
            filesystem_mode=filesystem_mode,
            thread_id=thread_id,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        # Skill loader. Placed before SubAgentMiddleware so subagents
        # inherit the same skill metadata (subagent specs reference the
        # same source paths via ``default_skills_sources()``).
        skills_mw,
        SubAgentMiddleware(backend=StateBackend, subagents=subagent_specs),
        # Tool selection (only when >30 tools and flag on).
        selector_mw,
        # Defensive caps, then prune, then summarize.
        model_call_limit_mw,
        tool_call_limit_mw,
        context_edit_mw,
        summarization_mw,
        # Provider compatibility + retry chain — placed after prune/compact
        # so retries happen on the already-trimmed payload.
        noop_mw,
        retry_mw,
        fallback_mw,
        # Coalesce a multi-text-block system message into one block
        # immediately before the model call. Sits innermost on the
        # system-message-mutation chain so it observes every appender
        # (todo / filesystem / skills / subagents …) and prevents
        # OpenRouter→Anthropic from redistributing ``cache_control``
        # across N blocks and tripping Anthropic's 4-breakpoint cap.
        # See ``middleware/flatten_system.py`` for full rationale.
        FlattenSystemMessageMiddleware(),
        # Tool-call repair must run after model emits but before
        # permission / dedup / doom-loop interpret the calls.
        repair_mw,
        # Permission deny/ask BEFORE the calls are forwarded to tool nodes.
        permission_mw,
        doom_loop_mw,
        # Action log sits inside permission so denied calls don't appear
        # as completions, and outside dedup so each unique tool invocation
        # gets its own row.
        action_log_mw,
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=list(tools)),
        # Plugin slot — sits at the tail so plugin-side transforms see the
        # final tool result. Prompt caching is now applied at LLM build time
        # via ``apply_litellm_prompt_caching`` (see prompt_caching.py), so no
        # caching middleware is needed here. Multiple plugins run in declared
        # order; loader filtered by the admin allowlist already.
        *plugin_middlewares,
    ]
    deepagent_middleware = [m for m in deepagent_middleware if m is not None]

    agent = create_agent(
        llm,
        system_prompt=final_system_prompt,
        tools=list(tools),
        middleware=deepagent_middleware,
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
    )
    return agent.with_config(
        {
            "recursion_limit": 10_000,
            "metadata": {
                "ls_integration": "deepagents",
                "versions": {"deepagents": deepagents_version},
            },
        }
    )
