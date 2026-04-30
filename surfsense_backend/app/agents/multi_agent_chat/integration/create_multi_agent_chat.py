"""Single entry: SurfSense connectors + multi-agent stack → compiled supervisor graph."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.chat_deepagent import _map_connectors_to_searchable_types
from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.feature_flags import get_flags
from app.agents.new_chat.filesystem_backends import build_backend_resolver
from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.agents.new_chat.tools.mcp_tool import load_mcp_tools
from app.db import ChatVisibility

from app.agents.multi_agent_chat.core.mcp_partition import (
    fetch_mcp_connector_metadata_maps,
    partition_mcp_tools_by_expert_route,
)
from app.agents.multi_agent_chat.core.registry import build_registry_dependencies
from app.agents.multi_agent_chat.middleware.supervisor_stack import build_supervisor_middleware_stack
from app.agents.multi_agent_chat.routing.supervisor_routing import build_supervisor_routing_tools
from app.agents.multi_agent_chat.supervisor import build_supervisor_agent

logger = logging.getLogger(__name__)


def _compile_supervisor_chat_blocking(
    *,
    llm: BaseChatModel,
    routing_tools: list[BaseTool],
    checkpointer: Checkpointer | None,
    backend_resolver: Any,
    filesystem_mode: Any,
    search_space_id: int,
    user_id: str,
    thread_id: str | None,
    thread_visibility: ChatVisibility,
    anon_session_id: str | None,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
    max_input_tokens: int | None,
) -> Any:
    """CPU-heavy: middleware assembly + ``create_agent`` (runs in a worker thread)."""
    flags = get_flags()
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
        flags=flags,
    )
    return build_supervisor_agent(
        llm,
        tools=routing_tools,
        checkpointer=checkpointer,
        thread_visibility=thread_visibility,
        middleware=middleware,
        context_schema=SurfSenseContextSchema,
    )


async def create_multi_agent_chat(
    llm: BaseChatModel,
    *,
    db_session: AsyncSession,
    search_space_id: int,
    user_id: str,
    checkpointer: Checkpointer | None = None,
    thread_id: str | None = None,
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
):
    """Build the full multi-agent chat graph (supervisor + domain subgraphs via routing tools).

    **Builtins** (:mod:`expert_agent.builtins`): registry-grouped **categories** (research, memory, deliverables).
    **Connectors** (:mod:`expert_agent.connectors`): **vendor integrations** — one subgraph per route in
    ``TOOL_NAMES_BY_CATEGORY`` (e.g. calendar, confluence, discord, dropbox, gmail, google_drive, luma, notion, onedrive, teams).

    MCP tools from ``new_chat`` (``load_mcp_tools``) are partitioned inside this package and attached only
    to the matching expert subgraphs — not to the supervisor tool list as raw MCP calls. Inclusion matches
    ``new_chat.tools.registry.build_tools_async``: all tools returned by ``load_mcp_tools`` are merged
    after partitioning (no extra inventory filter on MCP). Connector routing uses ``available_connectors``:
    pass explicitly, or provide ``connector_service`` so lists are resolved like
    ``create_surfsense_deep_agent`` (``get_available_connectors`` → searchable types).

    Deliverables (thread-scoped reports, podcasts, etc.) are registered only when ``thread_id`` is set.

    When ``surfsense_stack`` is true (default), the supervisor uses the same SurfSense middleware shell as
    ``new_chat`` (KB priority/tree, filesystem, compaction, permissions, etc.) except ``SubAgentMiddleware`` /
    ``task``, since experts are separate graphs behind routing tools. Graph compilation runs in
    ``asyncio.to_thread`` so heavy CPU work does not block the event loop.
    """
    resolved_connectors = available_connectors
    resolved_doc_types = available_document_types
    if connector_service is not None:
        try:
            if resolved_connectors is None:
                connector_types = await connector_service.get_available_connectors(
                    search_space_id
                )
                if connector_types:
                    resolved_connectors = _map_connectors_to_searchable_types(
                        connector_types
                    )
            if resolved_doc_types is None:
                resolved_doc_types = (
                    await connector_service.get_available_document_types(search_space_id)
                )
        except Exception as exc:
            logger.warning(
                "Failed to discover available connectors/document types: %s",
                exc,
            )

    mcp_tools_by_route: dict[str, list[BaseTool]] | None = None
    if include_mcp_tools:
        mcp_flat = await load_mcp_tools(db_session, search_space_id)
        id_map, name_map = await fetch_mcp_connector_metadata_maps(db_session, search_space_id)
        mcp_tools_by_route = partition_mcp_tools_by_expert_route(mcp_flat, id_map, name_map)

    registry_dependencies = build_registry_dependencies(
        db_session=db_session,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id or "",
        llm=llm,
        firecrawl_api_key=firecrawl_api_key,
        connector_service=connector_service,
        available_connectors=resolved_connectors,
        available_document_types=resolved_doc_types,
        thread_visibility=thread_visibility,
    )
    routing_tools = build_supervisor_routing_tools(
        llm,
        registry_dependencies=registry_dependencies,
        include_deliverables=thread_id is not None,
        mcp_tools_by_route=mcp_tools_by_route,
        available_connectors=resolved_connectors,
        thread_visibility=thread_visibility,
    )

    fs_sel = filesystem_selection or FilesystemSelection()
    backend_resolver = build_backend_resolver(fs_sel, search_space_id=search_space_id)

    if not surfsense_stack:
        return build_supervisor_agent(
            llm,
            tools=routing_tools,
            checkpointer=checkpointer,
            thread_visibility=thread_visibility,
        )

    return await asyncio.to_thread(
        _compile_supervisor_chat_blocking,
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
        available_connectors=resolved_connectors,
        available_document_types=resolved_doc_types,
        mentioned_document_ids=mentioned_document_ids,
        max_input_tokens=max_input_tokens,
    )
