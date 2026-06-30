"""Main-agent middleware list assembly: one line per slot.

The main agent is a pure router — both filesystem reads/writes AND knowledge-base
retrieval are owned by the ``knowledge_base`` subagent and reached via the
``task`` tool. That subagent runs the hybrid ``search_knowledge_base`` (rendering
``<retrieved_context>`` with ``[n]`` citation labels) and the FS tools on demand;
the main agent only sees the specialist's grounded summary. The stack here
computes the workspace tree, commits any subagent-side staged writes at end of
turn (cloud mode), and wires the supporting middleware.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any, cast

from deepagents import SubAgent
from deepagents.backends import StateBackend
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer

from app.agents.chat.multi_agent_chat.main_agent.middleware.memory import (
    build_memory_mw,
)
from app.agents.chat.multi_agent_chat.shared.feature_flags import AgentFeatureFlags
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import FilesystemMode
from app.agents.chat.multi_agent_chat.shared.middleware.anthropic_cache import (
    build_anthropic_cache_mw,
)
from app.agents.chat.multi_agent_chat.shared.middleware.compaction import (
    build_compaction_mw,
)
from app.agents.chat.multi_agent_chat.shared.middleware.patch_tool_calls import (
    build_patch_tool_calls_mw,
)
from app.agents.chat.multi_agent_chat.shared.middleware.resilience import (
    build_resilience_middlewares,
)
from app.agents.chat.multi_agent_chat.shared.middleware.todos import build_todos_mw
from app.agents.chat.multi_agent_chat.shared.permissions import (
    build_permission_mw,
)
from app.agents.chat.multi_agent_chat.subagents import (
    build_subagents,
    get_subagents_to_exclude,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.knowledge_base.agent import (
    NAME as KB_WRITE_NAME,
    READONLY_NAME as KB_READONLY_NAME,
    build_readonly_subagent as build_kb_readonly_subagent,
    build_subagent as build_kb_write_subagent,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.knowledge_base.ask_knowledge_base_tool import (
    build_ask_knowledge_base_tool,
)
from app.agents.chat.multi_agent_chat.subagents.builtins.knowledge_base.prompts import (
    load_description as load_kb_write_description,
)
from app.agents.chat.multi_agent_chat.subagents.middleware_stack import (
    build_subagent_middleware_stack,
)
from app.agents.chat.multi_agent_chat.subagents.shared.spec import (
    SURF_LAZY_SPEC_FACTORY_KEY,
)
from app.db import ChatVisibility
from app.utils.perf import get_perf_logger

from .action_log import build_action_log_mw
from .anonymous_document import build_anonymous_doc_mw
from .busy_mutex import build_busy_mutex_mw
from .checkpointed_subagent_middleware import (
    SurfSenseCheckpointedSubAgentMiddleware,
)
from .checkpointed_subagent_middleware.task_description import (
    TASK_TOOL_DESCRIPTION,
)
from .context_editing import build_context_editing_mw
from .dedup_hitl import build_dedup_hitl_mw
from .doom_loop import build_doom_loop_mw
from .kb_persistence import build_kb_persistence_mw
from .knowledge_tree import build_knowledge_tree_mw
from .noop_injection import build_noop_injection_mw
from .otel_span import build_otel_mw
from .plugins import build_plugin_middlewares
from .skills import build_skills_mw
from .tool_call_repair import build_repair_mw

_perf_log = get_perf_logger()


def build_main_agent_deepagent_middleware(
    *,
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    workspace_id: int,
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
    mcp_tools_by_agent: dict[str, list[BaseTool]] | None = None,
    disabled_tools: list[str] | None = None,
) -> list[Any]:
    """Ordered middleware for ``create_agent`` (None entries already stripped)."""
    stack_build_start = time.perf_counter()
    resilience = build_resilience_middlewares(flags)

    memory_mw = build_memory_mw(
        user_id=user_id,
        workspace_id=workspace_id,
        visibility=visibility,
    )

    subagent_dependencies = {
        **subagent_dependencies,
        "backend_resolver": backend_resolver,
        "filesystem_mode": filesystem_mode,
        "flags": flags,
    }
    shared_mw_start = time.perf_counter()
    shared_subagent_middleware = build_subagent_middleware_stack(
        resilience=resilience,
        flags=flags,
    )
    shared_mw_elapsed = time.perf_counter() - shared_mw_start

    def _compile_kb_readonly() -> Runnable:
        """Build *and* compile the read-only KB graph on first ``ask_knowledge_base`` use.

        Both the spec build (``build_kb_readonly_subagent`` — middleware +
        tool-schema construction, ~the same cost as one regular subagent) and
        the ``create_agent`` compile are deferred here (memoized by
        ``build_ask_knowledge_base_tool``) so neither is paid on the cold
        agent-build / TTFT path; most first turns never call a subagent.
        """
        build_start = time.perf_counter()
        kb_readonly_spec = build_kb_readonly_subagent(
            dependencies=subagent_dependencies,
            model=llm,
            middleware_stack=shared_subagent_middleware,
        ).spec
        runnable = create_agent(
            llm,
            system_prompt=kb_readonly_spec["system_prompt"],
            tools=kb_readonly_spec["tools"],
            middleware=kb_readonly_spec["middleware"],
            name=KB_READONLY_NAME,
            checkpointer=checkpointer,
        )
        _perf_log.info(
            "[subagent_compile_lazy] name=%s (spec+compile) in %.3fs",
            KB_READONLY_NAME,
            time.perf_counter() - build_start,
        )
        return runnable

    ask_kb_tool = build_ask_knowledge_base_tool(_compile_kb_readonly)

    def _build_kb_write_spec() -> dict[str, Any]:
        """Build the *write* knowledge_base subagent spec on first ``task`` use.

        The KB filesystem middleware builds ~13 tool schemas at ~150ms each
        (~2s total), all of which used to land on the cold agent-build / TTFT
        path even though ``task("knowledge_base")`` is essentially never the
        first thing a turn does. Deferring the whole spec build here (memoized
        by the checkpointed subagent middleware) moves that cost to the first
        actual KB-write delegation. Captures the same ``subagent_dependencies``
        the eager build would have used, so cross-thread cache behaviour is
        unchanged.
        """
        spec = build_kb_write_subagent(
            dependencies=subagent_dependencies,
            model=llm,
            middleware_stack=shared_subagent_middleware,
        ).spec
        if disabled_tools:
            disabled = frozenset(disabled_tools)
            tools = spec.get("tools")  # type: ignore[typeddict-item]
            if isinstance(tools, list):
                spec["tools"] = [  # type: ignore[typeddict-unknown-key]
                    t for t in tools if getattr(t, "name", None) not in disabled
                ]
        return cast(dict[str, Any], spec)

    subagents_start = time.perf_counter()
    # The write knowledge_base subagent is excluded from the eager build and
    # registered as a lazy descriptor (name + description cheap; spec built on
    # first ``task("knowledge_base")`` use) — see ``_build_kb_write_spec``.
    exclude_names = [*get_subagents_to_exclude(available_connectors), KB_WRITE_NAME]
    subagents: list[SubAgent] = build_subagents(
        dependencies=subagent_dependencies,
        model=llm,
        middleware_stack=shared_subagent_middleware,
        mcp_tools_by_agent=mcp_tools_by_agent or {},
        exclude=exclude_names,
        disabled_tools=disabled_tools,
        ask_kb_tool=ask_kb_tool,
    )
    kb_write_descriptor = cast(
        SubAgent,
        {
            "name": KB_WRITE_NAME,
            "description": load_kb_write_description(),
            SURF_LAZY_SPEC_FACTORY_KEY: _build_kb_write_spec,
        },
    )
    subagents.append(kb_write_descriptor)
    subagents_elapsed = time.perf_counter() - subagents_start
    logging.debug("Subagents registry: %s", [s["name"] for s in subagents])

    assembly_start = time.perf_counter()
    stack: list[Any] = [
        build_busy_mutex_mw(flags),
        build_otel_mw(flags),
        build_todos_mw(system_prompt=""),
        memory_mw,
        build_anonymous_doc_mw(
            filesystem_mode=filesystem_mode, anon_session_id=anon_session_id
        ),
        build_knowledge_tree_mw(
            filesystem_mode=filesystem_mode,
            workspace_id=workspace_id,
            llm=llm,
        ),
        build_kb_persistence_mw(
            filesystem_mode=filesystem_mode,
            workspace_id=workspace_id,
            user_id=user_id,
            thread_id=thread_id,
        ),
        build_skills_mw(
            flags=flags,
            filesystem_mode=filesystem_mode,
            workspace_id=workspace_id,
        ),
        SurfSenseCheckpointedSubAgentMiddleware(
            checkpointer=checkpointer,
            backend=StateBackend,
            subagents=subagents,
            system_prompt=None,
            task_description=TASK_TOOL_DESCRIPTION,
            workspace_id=workspace_id,
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
        build_permission_mw(flags=flags),
        build_doom_loop_mw(flags),
        build_action_log_mw(
            flags=flags,
            thread_id=thread_id,
            workspace_id=workspace_id,
            user_id=user_id,
        ),
        build_patch_tool_calls_mw(),
        build_dedup_hitl_mw(tools),
        *build_plugin_middlewares(
            flags=flags,
            workspace_id=workspace_id,
            user_id=user_id,
            visibility=visibility,
            llm=llm,
        ),
        build_anthropic_cache_mw(),
    ]
    result = [m for m in stack if m is not None]
    assembly_elapsed = time.perf_counter() - assembly_start
    _perf_log.info(
        "[stack_build] total=%.3fs shared_subagent_mw=%.3fs "
        "build_subagents=%.3fs stack_assembly=%.3fs subagents=%d mw=%d "
        "(kb_readonly deferred to first ask_knowledge_base)",
        time.perf_counter() - stack_build_start,
        shared_mw_elapsed,
        subagents_elapsed,
        assembly_elapsed,
        len(subagents),
        len(result),
    )
    return result
