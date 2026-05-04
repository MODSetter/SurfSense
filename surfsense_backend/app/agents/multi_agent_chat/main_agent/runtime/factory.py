"""Async factory: tools, system prompt, MCP buckets for subagents, then sync graph compile."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Any

from deepagents.graph import BASE_AGENT_PROMPT
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from ..graph.compile_graph_sync import build_compiled_agent_graph_sync
from ..tools import MAIN_AGENT_SURFSENSE_TOOL_NAMES, MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED
from app.agents.multi_agent_chat.subagents.mcp_tools.index import (
    load_mcp_tools_by_connector,
)
from app.agents.new_chat.chat_deepagent import _map_connectors_to_searchable_types
from app.agents.new_chat.feature_flags import AgentFeatureFlags, get_flags
from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import FilesystemMode, FilesystemSelection
from app.agents.new_chat.llm_config import AgentConfig
from app.agents.multi_agent_chat.subagents import (
    get_subagents_to_exclude,
    main_prompt_registry_subagent_lines,
)
from ..system_prompt import build_main_agent_system_prompt
from app.agents.new_chat.tools.invalid_tool import INVALID_TOOL_NAME, invalid_tool
from app.agents.new_chat.tools.registry import build_tools_async
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


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
    """Deep agent with SurfSense tools/middleware; registry route subagents behind ``task`` when enabled."""
    _t_agent_total = time.perf_counter()
    filesystem_selection = filesystem_selection or FilesystemSelection()
    backend_resolver = build_backend_resolver(
        filesystem_selection,
        search_space_id=search_space_id
        if filesystem_selection.mode == FilesystemMode.CLOUD
        else None,
    )

    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        connector_types = await connector_service.get_available_connectors(
            search_space_id
        )
        available_connectors = _map_connectors_to_searchable_types(connector_types)

        available_document_types = await connector_service.get_available_document_types(
            search_space_id
        )

    except Exception as e:
        logging.warning("Failed to discover available connectors/document types: %s", e)
    _perf_log.info(
        "[create_agent] Connector/doc-type discovery in %.3fs",
        time.perf_counter() - _t0,
    )

    visibility = thread_visibility or ChatVisibility.PRIVATE

    _model_profile = getattr(llm, "profile", None)
    _max_input_tokens: int | None = (
        _model_profile.get("max_input_tokens")
        if isinstance(_model_profile, dict)
        else None
    )

    dependencies: dict[str, Any] = {
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

    _t0 = time.perf_counter()
    mcp_tools_by_agent = await load_mcp_tools_by_connector(db_session, search_space_id)
    _perf_log.info(
        "[create_agent] load_mcp_tools_by_connector in %.3fs (%d buckets)",
        time.perf_counter() - _t0,
        len(mcp_tools_by_agent),
    )

    modified_disabled_tools = list(disabled_tools) if disabled_tools else []

    if "search_knowledge_base" not in modified_disabled_tools:
        modified_disabled_tools.append("search_knowledge_base")

    if enabled_tools is not None:
        main_agent_enabled_tools = [
            n for n in enabled_tools if n in MAIN_AGENT_SURFSENSE_TOOL_NAMES
        ]
    else:
        main_agent_enabled_tools = list(MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED)

    _t0 = time.perf_counter()
    tools = await build_tools_async(
        dependencies=dependencies,
        enabled_tools=main_agent_enabled_tools,
        disabled_tools=modified_disabled_tools,
        additional_tools=list(additional_tools) if additional_tools else None,
        include_mcp_tools=False,
    )

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

    _t0 = time.perf_counter()
    _enabled_tool_names = {t.name for t in tools}
    _user_disabled_tool_names = set(disabled_tools) if disabled_tools else set()

    _model_name: str | None = None
    prof = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    if isinstance(prof, str):
        _model_name = prof

    _connector_exclude = get_subagents_to_exclude(available_connectors)
    _registry_subagent_prompt_lines = main_prompt_registry_subagent_lines(
        _connector_exclude
    )

    if agent_config is not None:
        system_prompt = build_main_agent_system_prompt(
            today=None,
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            custom_system_instructions=agent_config.system_instructions,
            use_default_system_instructions=agent_config.use_default_system_instructions,
            citations_enabled=agent_config.citations_enabled,
            model_name=_model_name or getattr(agent_config, "model_name", None),
            registry_subagent_prompt_lines=_registry_subagent_prompt_lines,
        )
    else:
        system_prompt = build_main_agent_system_prompt(
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            citations_enabled=True,
            model_name=_model_name,
            registry_subagent_prompt_lines=_registry_subagent_prompt_lines,
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT

    _t0 = time.perf_counter()
    agent = await asyncio.to_thread(
        build_compiled_agent_graph_sync,
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
        mentioned_document_ids=mentioned_document_ids,
        max_input_tokens=_max_input_tokens,
        flags=_flags,
        checkpointer=checkpointer,
        subagent_dependencies=dependencies,
        mcp_tools_by_agent=mcp_tools_by_agent,
        disabled_tools=disabled_tools,
    )
    _perf_log.info(
        "[create_agent] Middleware stack + graph compiled in %.3fs",
        time.perf_counter() - _t0,
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent
