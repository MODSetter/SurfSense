"""Synchronous graph compile (middleware + ``create_agent``)."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from deepagents import __version__ as deepagents_version
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.chat.multi_agent_chat.main_agent.middleware.stack import (
    build_main_agent_deepagent_middleware,
)
from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.shared.context import SurfSenseContextSchema
from app.db import ChatVisibility
from app.utils.perf import get_perf_logger

_perf_log = get_perf_logger()


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
    mcp_tools_by_agent: dict[str, list[BaseTool]] | None = None,
    disabled_tools: list[str] | None = None,
):
    """Sync compile: middleware + ``create_agent`` (run via ``asyncio.to_thread``)."""
    mw_start = time.perf_counter()
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
        disabled_tools=disabled_tools,
    )
    mw_elapsed = time.perf_counter() - mw_start

    create_start = time.perf_counter()
    agent = create_agent(
        llm,
        system_prompt=final_system_prompt,
        tools=list(tools),
        middleware=main_agent_middleware,
        context_schema=SurfSenseContextSchema,
        checkpointer=checkpointer,
    )
    create_elapsed = time.perf_counter() - create_start
    _perf_log.info(
        "[graph_compile] middleware_build=%.3fs main_create_agent=%.3fs "
        "total=%.3fs mw_count=%d",
        mw_elapsed,
        create_elapsed,
        mw_elapsed + create_elapsed,
        len(main_agent_middleware),
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
