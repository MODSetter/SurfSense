"""Main-agent middleware list assembly: one line per slot."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent
from deepagents.backends import StateBackend
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.multi_agent_chat.subagents import (
    build_subagents,
    get_subagents_to_exclude,
)
from app.agents.multi_agent_chat.subagents.builtins.general_purpose.agent import (
    build_subagent as build_general_purpose_subagent,
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
from .main_agent.selector import build_selector_mw
from .main_agent.skills import build_skills_mw
from .shared.anthropic_cache import build_anthropic_cache_mw
from .shared.compaction import build_compaction_mw
from .shared.file_intent import build_file_intent_mw
from .shared.filesystem import build_filesystem_mw
from .shared.memory import build_memory_mw
from .shared.patch_tool_calls import build_patch_tool_calls_mw
from .shared.permissions import (
    build_full_permission_mw,
    build_permission_context,
)
from .shared.resilience import build_resilience_bundle
from .shared.todos import build_todos_mw
from .subagent.extras import build_subagent_extras


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
    permissions = build_permission_context(
        flags=flags,
        filesystem_mode=filesystem_mode,
        tools=tools,
        available_connectors=available_connectors,
    )
    resilience = build_resilience_bundle(flags)

    # Single instance threaded into both the main-agent stack and the general-purpose subagent.
    memory_mw = build_memory_mw(
        user_id=user_id,
        search_space_id=search_space_id,
        visibility=visibility,
    )

    general_purpose_subagent = build_general_purpose_subagent(
        llm=llm,
        tools=tools,
        backend_resolver=backend_resolver,
        filesystem_mode=filesystem_mode,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id,
        permissions=permissions,
        resilience=resilience,
        memory_mw=memory_mw,
    )

    subagents_registry: list[SubAgent] = []
    try:
        subagent_extras = build_subagent_extras(
            permissions=permissions,
            resilience=resilience,
        )
        subagents_registry = build_subagents(
            dependencies=subagent_dependencies,
            model=llm,
            extra_middleware=subagent_extras,
            mcp_tools_by_agent=mcp_tools_by_agent or {},
            exclude=get_subagents_to_exclude(available_connectors),
            disabled_tools=disabled_tools,
        )
        logging.debug(
            "Subagents registry: %s",
            [s["name"] for s in subagents_registry],
        )
    except Exception:
        # Degrade to general-purpose-only rather than aborting the turn:
        # one bad subagent dep should not deny the user a response.
        logging.exception(
            "Subagents registry build failed; falling back to general-purpose only"
        )
        subagents_registry = []

    subagents: list[SubAgent] = [general_purpose_subagent, *subagents_registry]

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
        build_file_intent_mw(llm),
        build_filesystem_mw(
            backend_resolver=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            user_id=user_id,
            thread_id=thread_id,
        ),
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
        ),
        build_selector_mw(flags=flags, tools=tools),
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
        build_full_permission_mw(permissions.rulesets),
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
