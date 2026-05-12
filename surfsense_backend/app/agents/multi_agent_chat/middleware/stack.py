"""Main-agent middleware list assembly: one line per slot.

The main agent is a pure router — filesystem reads/writes are owned by the
``knowledge_base`` subagent and delegated via the ``task`` tool. The stack
here only renders KB context (workspace tree + priority docs), projects it
into system messages, and commits any subagent-side staged writes at end of
turn (cloud mode).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent
from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.multi_agent_chat.subagents import (
    build_subagents,
    get_subagents_to_exclude,
)
from app.agents.multi_agent_chat.subagents.builtins.knowledge_base.agent import (
    READONLY_NAME as KB_READONLY_NAME,
    build_readonly_subagent as build_kb_readonly_subagent,
)
from app.agents.multi_agent_chat.subagents.builtins.knowledge_base.ask_knowledge_base_tool import (
    build_ask_knowledge_base_tool,
)
from app.agents.multi_agent_chat.subagents.shared.permissions import ToolsPermissions
from app.agents.new_chat.feature_flags import AgentFeatureFlags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.db import ChatVisibility

from .main_agent.action_log import build_action_log_mw
from .main_agent.anonymous_doc import build_anonymous_doc_mw
from .main_agent.busy_mutex import build_busy_mutex_mw
from .main_agent.checkpointed_subagent_middleware import (
    SurfSenseCheckpointedSubAgentMiddleware,
)
from .main_agent.checkpointed_subagent_middleware.task_description import (
    TASK_TOOL_DESCRIPTION,
)
from .main_agent.context_editing import build_context_editing_mw
from .main_agent.dedup_hitl import build_dedup_hitl_mw
from .main_agent.doom_loop import build_doom_loop_mw
from .main_agent.kb_persistence import build_kb_persistence_mw
from .main_agent.knowledge_priority import build_knowledge_priority_mw
from .main_agent.knowledge_tree import build_knowledge_tree_mw
from .main_agent.noop_injection import build_noop_injection_mw
from .main_agent.otel import build_otel_mw
from .main_agent.plugins import build_plugin_middlewares
from .main_agent.repair import build_repair_mw
from .main_agent.skills import build_skills_mw
from .shared.anthropic_cache import build_anthropic_cache_mw
from .shared.compaction import build_compaction_mw
from .shared.kb_context_projection import build_kb_context_projection_mw
from .shared.memory import build_memory_mw
from .shared.patch_tool_calls import build_patch_tool_calls_mw
from .shared.resilience import build_resilience_middlewares
from .shared.todos import build_todos_mw
from .subagent.middleware_stack import build_subagent_middleware_stack


def build_main_agent_deepagent_middleware(
    *,
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
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
    subagent_dependencies: dict[str, Any],
    checkpointer: Checkpointer,
    mcp_tools_by_agent: dict[str, ToolsPermissions] | None = None,
    disabled_tools: list[str] | None = None,
) -> list[Any]:
    """Ordered middleware for ``create_agent`` (None entries already stripped)."""
    resilience = build_resilience_middlewares(flags)

    memory_mw = build_memory_mw(
        user_id=user_id,
        search_space_id=search_space_id,
        visibility=visibility,
    )

    subagent_dependencies = {
        **subagent_dependencies,
        "backend_resolver": backend_resolver,
        "filesystem_mode": filesystem_mode,
    }
    shared_subagent_middleware = build_subagent_middleware_stack(resilience=resilience)

    kb_readonly_spec = build_kb_readonly_subagent(
        dependencies=subagent_dependencies,
        model=llm,
        middleware_stack=shared_subagent_middleware,
    )
    kb_readonly_runnable = create_agent(
        llm,
        system_prompt=kb_readonly_spec["system_prompt"],
        tools=kb_readonly_spec["tools"],
        middleware=kb_readonly_spec["middleware"],
        name=KB_READONLY_NAME,
        checkpointer=checkpointer,
    )
    ask_kb_tool = build_ask_knowledge_base_tool(kb_readonly_runnable)

    subagents: list[SubAgent] = build_subagents(
        dependencies=subagent_dependencies,
        model=llm,
        middleware_stack=shared_subagent_middleware,
        mcp_tools_by_agent=mcp_tools_by_agent or {},
        exclude=get_subagents_to_exclude(available_connectors),
        disabled_tools=disabled_tools,
        ask_kb_tool=ask_kb_tool,
    )
    logging.debug("Subagents registry: %s", [s["name"] for s in subagents])

    stack: list[Any] = [
        build_busy_mutex_mw(flags),
        build_otel_mw(flags),
        build_todos_mw(),
        memory_mw,
        build_anonymous_doc_mw(
            filesystem_mode=filesystem_mode, anon_session_id=anon_session_id
        ),
        build_knowledge_tree_mw(
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            llm=llm,
        ),
        build_knowledge_priority_mw(
            llm=llm,
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
        ),
        build_kb_context_projection_mw(),
        build_kb_persistence_mw(
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            user_id=user_id,
            thread_id=thread_id,
        ),
        build_skills_mw(
            flags=flags,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
        ),
        SurfSenseCheckpointedSubAgentMiddleware(
            checkpointer=checkpointer,
            backend=StateBackend,
            subagents=subagents,
            system_prompt=None,
            task_description=TASK_TOOL_DESCRIPTION,
        ),
        resilience.model_call_limit,
        resilience.tool_call_limit,
        build_context_editing_mw(
            flags=flags,
            max_input_tokens=max_input_tokens,
            tools=tools,
            backend_resolver=backend_resolver,
        ),
        build_compaction_mw(llm),
        build_noop_injection_mw(flags),
        resilience.retry,
        resilience.fallback,
        build_repair_mw(flags=flags, tools=tools),
        build_doom_loop_mw(flags),
        build_action_log_mw(
            flags=flags,
            thread_id=thread_id,
            search_space_id=search_space_id,
            user_id=user_id,
        ),
        build_patch_tool_calls_mw(),
        build_dedup_hitl_mw(tools),
        *build_plugin_middlewares(
            flags=flags,
            search_space_id=search_space_id,
            user_id=user_id,
            visibility=visibility,
            llm=llm,
        ),
        build_anthropic_cache_mw(),
    ]
    return [m for m in stack if m is not None]
