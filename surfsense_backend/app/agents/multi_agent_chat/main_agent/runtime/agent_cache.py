"""Compiled agent graph caching for the multi-agent path."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.multi_agent_chat.subagents.shared.permissions import ToolsPermissions
from app.agents.new_chat.agent_cache import (
    flags_signature,
    get_cache,
    stable_hash,
    system_prompt_hash,
    tools_signature,
)
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.db import ChatVisibility

from ..graph.compile_graph_sync import build_compiled_agent_graph_sync


def mcp_signature(mcp_tools_by_agent: dict[str, ToolsPermissions]) -> str:
    """Hash the per-agent MCP tool surface so a change rotates the cache key."""
    rows = []
    for agent_name in sorted(mcp_tools_by_agent.keys()):
        perms = mcp_tools_by_agent[agent_name]
        allow_names = sorted(item.get("name", "") for item in perms.get("allow", []))
        ask_names = sorted(item.get("name", "") for item in perms.get("ask", []))
        rows.append((agent_name, allow_names, ask_names))
    return stable_hash(rows)


async def build_agent_with_cache(
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
    available_connectors: list[str],
    available_document_types: list[str],
    mentioned_document_ids: list[int] | None,
    max_input_tokens: int | None,
    flags: AgentFeatureFlags,
    checkpointer: Checkpointer,
    subagent_dependencies: dict[str, Any],
    mcp_tools_by_agent: dict[str, ToolsPermissions],
    disabled_tools: list[str] | None,
    config_id: str | None,
) -> Any:
    """Compile the multi-agent graph, serving from cache when key components are stable."""

    async def _build() -> Any:
        return await asyncio.to_thread(
            build_compiled_agent_graph_sync,
            llm=llm,
            tools=tools,
            final_system_prompt=final_system_prompt,
            backend_resolver=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            user_id=user_id,
            thread_id=thread_id,
            visibility=visibility,
            anon_session_id=anon_session_id,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
            max_input_tokens=max_input_tokens,
            flags=flags,
            checkpointer=checkpointer,
            subagent_dependencies=subagent_dependencies,
            mcp_tools_by_agent=mcp_tools_by_agent,
            disabled_tools=disabled_tools,
        )

    if not (flags.enable_agent_cache and not flags.disable_new_agent_stack):
        return await _build()

    # Every per-request value any middleware closes over at __init__ must be in
    # the key, otherwise a hit will leak state across threads. Bump the schema
    # version when the component list changes shape.
    cache_key = stable_hash(
        "multi-agent-v1",
        config_id,
        thread_id,
        user_id,
        search_space_id,
        visibility,
        filesystem_mode,
        anon_session_id,
        tools_signature(
            tools,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
        ),
        mcp_signature(mcp_tools_by_agent),
        flags_signature(flags),
        system_prompt_hash(final_system_prompt),
        max_input_tokens,
        sorted(disabled_tools) if disabled_tools else None,
    )
    return await get_cache().get_or_build(cache_key, builder=_build)


__all__ = ["build_agent_with_cache", "mcp_signature"]
