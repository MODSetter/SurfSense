"""Single entry: SurfSense connectors + multi-agent stack → compiled supervisor graph."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import ChatVisibility

from app.agents.new_chat.tools.mcp_tool import load_mcp_tools

from app.agents.multi_agent_chat.core.mcp_partition import (
    fetch_mcp_connector_metadata_maps,
    partition_mcp_tools_by_expert_route,
)
from app.agents.multi_agent_chat.core.registry import build_registry_dependencies
from app.agents.multi_agent_chat.routing.supervisor_routing import build_supervisor_routing_tools
from app.agents.multi_agent_chat.supervisor import build_supervisor_agent


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
):
    """Build the full multi-agent chat graph (supervisor + domain subgraphs via routing tools).

    **Builtins** (:mod:`expert_agent.builtins`): registry-grouped **categories** (research, memory, deliverables).
    **Connectors** (:mod:`expert_agent.connectors`): **vendor integrations** — one subgraph each where split
    (e.g. Gmail, Calendar, Discord, Teams, Notion, Confluence, Google Drive, Dropbox, OneDrive, Luma).

    MCP tools from ``new_chat`` (``load_mcp_tools``) are partitioned inside this package and attached only
    to the matching expert subgraphs — not to the supervisor tool list as raw MCP calls.

    Deliverables (thread-scoped reports, podcasts, etc.) are registered only when ``thread_id`` is set.
    """
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
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        thread_visibility=thread_visibility,
    )
    routing_tools = build_supervisor_routing_tools(
        llm,
        registry_dependencies=registry_dependencies,
        include_deliverables=thread_id is not None,
        mcp_tools_by_route=mcp_tools_by_route,
    )
    return build_supervisor_agent(llm, tools=routing_tools, checkpointer=checkpointer)
