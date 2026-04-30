"""Build the multi-agent supervisor graph: MCP partition, registry, routing tools, optional SurfSense middleware."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.multi_agent_chat.core.mcp_partition import (
    fetch_mcp_connector_metadata_maps,
    partition_mcp_tools_by_expert_route,
)
from app.agents.multi_agent_chat.core.registry.dependencies import (
    build_registry_dependencies,
    coerce_thread_id_for_registry,
)
from app.agents.multi_agent_chat.middleware.supervisor_stack import (
    build_supervisor_middleware_stack,
)
from app.agents.multi_agent_chat.routing.supervisor_routing import (
    build_supervisor_routing_tools,
)
from app.agents.multi_agent_chat.supervisor import build_supervisor_agent
from app.agents.new_chat.chat_deepagent import _map_connectors_to_searchable_types
from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.feature_flags import get_flags
from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.agents.new_chat.tools.mcp_tool import load_mcp_tools
from app.db import ChatVisibility

logger = logging.getLogger(__name__)


async def _discover_connectors_and_doc_types(
    *,
    connector_service: Any | None,
    search_space_id: int,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
) -> tuple[list[str] | None, list[str] | None]:
    """Fill connector / document-type lists from ``connector_service`` when callers omit them."""
    connectors = available_connectors
    doc_types = available_document_types
    if connector_service is None:
        return connectors, doc_types
    try:
        if connectors is None:
            raw = await connector_service.get_available_connectors(search_space_id)
            if raw:
                connectors = _map_connectors_to_searchable_types(raw)
        if doc_types is None:
            doc_types = await connector_service.get_available_document_types(search_space_id)
    except Exception as exc:
        logger.warning("Failed to discover available connectors/document types: %s", exc)
    return connectors, doc_types


async def _mcp_tools_by_expert_route(
    *,
    db_session: AsyncSession,
    search_space_id: int,
) -> dict[str, list[BaseTool]] | None:
    mcp_flat = await load_mcp_tools(db_session, search_space_id)
    id_map, name_map = await fetch_mcp_connector_metadata_maps(db_session, search_space_id)
    return partition_mcp_tools_by_expert_route(mcp_flat, id_map, name_map)


def _make_supervisor_routing_tools(
    llm: BaseChatModel,
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
    thread_id: str | int | None,
    firecrawl_api_key: str | None,
    connector_service: Any | None,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    thread_visibility: ChatVisibility,
    mcp_tools_by_route: dict[str, list[BaseTool]] | None,
) -> list[BaseTool]:
    registry_dependencies = build_registry_dependencies(
        db_session=db_session,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id,
        llm=llm,
        firecrawl_api_key=firecrawl_api_key,
        connector_service=connector_service,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        thread_visibility=thread_visibility,
    )
    return build_supervisor_routing_tools(
        llm,
        registry_dependencies=registry_dependencies,
        include_deliverables=coerce_thread_id_for_registry(thread_id) is not None,
        mcp_tools_by_route=mcp_tools_by_route,
        available_connectors=available_connectors,
        thread_visibility=thread_visibility,
    )


def _compile_supervisor_agent_sync(
    *,
    llm: BaseChatModel,
    routing_tools: list[BaseTool],
    checkpointer: Checkpointer | None,
    backend_resolver: Any,
    filesystem_mode: Any,
    search_space_id: int,
    user_id: str,
    thread_id: str | int | None,
    thread_visibility: ChatVisibility,
    anon_session_id: str | None,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
    max_input_tokens: int | None,
    citations_enabled: bool,
) -> Any:
    """CPU-heavy: middleware stack + ``create_agent`` (intended for ``asyncio.to_thread``)."""
    middleware = build_supervisor_middleware_stack(
        llm=llm,
        tools=routing_tools,
        backend_resolver=backend_resolver,
        filesystem_mode=filesystem_mode,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id,
        visibility=thread_visibility,
        anon_session_id=anon_session_id,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        mentioned_document_ids=mentioned_document_ids,
        max_input_tokens=max_input_tokens,
        flags=get_flags(),
    )
    return build_supervisor_agent(
        llm,
        tools=routing_tools,
        checkpointer=checkpointer,
        thread_visibility=thread_visibility,
        middleware=middleware,
        context_schema=SurfSenseContextSchema,
        citations_enabled=citations_enabled,
    )


async def create_multi_agent_chat(
    llm: BaseChatModel,
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
    checkpointer: Checkpointer | None = None,
    thread_id: str | int | None = None,
    firecrawl_api_key: str | None = None,
    connector_service: Any | None = None,
    available_connectors: list[str] | None = None,
    available_document_types: list[str] | None = None,
    thread_visibility: ChatVisibility = ChatVisibility.PRIVATE,
    include_mcp_tools: bool = True,
    filesystem_selection: FilesystemSelection | None = None,
    anon_session_id: str | None = None,
    mentioned_document_ids: list[int] | None = None,
    max_input_tokens: int | None = None,
    surfsense_stack: bool = True,
    citations_enabled: bool | None = None,
):
    """Build the full multi-agent chat graph (supervisor + expert subgraphs via routing tools).

    **Builtins** (:mod:`expert_agent.builtins`): registry-grouped **categories** (research, memory, deliverables).
    **Connectors** (:mod:`expert_agent.connectors`): **vendor integrations** — one subgraph per route in
    ``TOOL_NAMES_BY_CATEGORY`` (e.g. calendar, confluence, discord, dropbox, gmail, google_drive, luma, notion, onedrive, teams).

    MCP tools (via ``load_mcp_tools``) are partitioned inside this package and attached only
    to the matching expert subgraphs — not to the supervisor tool list as raw MCP calls. Inclusion matches
    ``app.agents.new_chat.tools.registry.build_tools_async``: all tools returned by ``load_mcp_tools`` are merged
    after partitioning (no extra inventory filter on MCP). Connector routing uses ``available_connectors``:
    pass explicitly, or provide ``connector_service`` so lists are resolved like
    ``create_surfsense_deep_agent`` (``get_available_connectors`` → searchable types).

    Deliverables (thread-scoped reports, podcasts, etc.) are registered only when ``thread_id`` is set.

    When ``surfsense_stack`` is true (default), the supervisor uses the same SurfSense middleware shell as
    the main single-agent chat (KB priority/tree, filesystem, compaction, permissions, etc.) except
    ``SubAgentMiddleware`` / ``task``, since experts are separate graphs behind routing tools. Graph
    compilation runs in ``asyncio.to_thread`` so heavy CPU work does not block the event loop.

    ``citations_enabled``: when ``None``, defaults to ``True`` (same default as ``AgentConfig`` / main chat).
    """
    citations = True if citations_enabled is None else citations_enabled
    connectors, doc_types = await _discover_connectors_and_doc_types(
        connector_service=connector_service,
        search_space_id=search_space_id,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
    )

    mcp_by_route: dict[str, list[BaseTool]] | None = None
    if include_mcp_tools:
        mcp_by_route = await _mcp_tools_by_expert_route(
            db_session=db_session, search_space_id=search_space_id
        )

    routing_tools = _make_supervisor_routing_tools(
        llm,
        db_session=db_session,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id,
        firecrawl_api_key=firecrawl_api_key,
        connector_service=connector_service,
        available_connectors=connectors,
        available_document_types=doc_types,
        thread_visibility=thread_visibility,
        mcp_tools_by_route=mcp_by_route,
    )

    fs_sel = filesystem_selection or FilesystemSelection()
    backend_resolver = build_backend_resolver(fs_sel, search_space_id=search_space_id)

    if not surfsense_stack:
        return build_supervisor_agent(
            llm,
            tools=routing_tools,
            checkpointer=checkpointer,
            thread_visibility=thread_visibility,
            citations_enabled=citations,
        )

    return await asyncio.to_thread(
        _compile_supervisor_agent_sync,
        llm=llm,
        routing_tools=routing_tools,
        checkpointer=checkpointer,
        backend_resolver=backend_resolver,
        filesystem_mode=fs_sel.mode,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id,
        thread_visibility=thread_visibility,
        anon_session_id=anon_session_id,
        available_connectors=connectors,
        available_document_types=doc_types,
        mentioned_document_ids=mentioned_document_ids,
        max_input_tokens=max_input_tokens,
        citations_enabled=citations,
    )
