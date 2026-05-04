"""Synchronous graph compile (middleware + ``create_agent``)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from deepagents import __version__ as deepagents_version
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from .middleware import build_main_agent_deepagent_middleware
from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)
from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.db import ChatVisibility


def build_compiled_agent_graph_sync(
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
    subagent_dependencies: dict[str, Any],
    mcp_tools_by_agent: dict[str, ToolsPermissions] | None = None,
):
    """Sync compile: middleware + ``create_agent`` (run via ``asyncio.to_thread``)."""
    main_agent_middleware = build_main_agent_deepagent_middleware(
        llm=llm,
        tools=tools,
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
        subagent_dependencies=subagent_dependencies,
        checkpointer=checkpointer,
        mcp_tools_by_agent=mcp_tools_by_agent,
    )

    agent = create_agent(
        llm,
        system_prompt=final_system_prompt,
        tools=list(tools),
        middleware=main_agent_middleware,
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
