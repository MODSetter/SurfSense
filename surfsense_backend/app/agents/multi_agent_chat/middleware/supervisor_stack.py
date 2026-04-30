"""Supervisor middleware stack matching the main single-agent chat (no ``SubAgentMiddleware`` / ``task``)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from deepagents.backends import StateBackend
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from langchain.agents.middleware import (
    LLMToolSelectorMiddleware,
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from app.agents.new_chat.feature_flags import AgentFeatureFlags, get_flags
from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.middleware import (
    ActionLogMiddleware,
    AnonymousDocumentMiddleware,
    BusyMutexMiddleware,
    ClearToolUsesEdit,
    DedupHITLToolCallsMiddleware,
    DoomLoopMiddleware,
    FileIntentMiddleware,
    KnowledgeBasePersistenceMiddleware,
    KnowledgePriorityMiddleware,
    KnowledgeTreeMiddleware,
    MemoryInjectionMiddleware,
    NoopInjectionMiddleware,
    OtelSpanMiddleware,
    RetryAfterMiddleware,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
    SurfSenseFilesystemMiddleware,
    ToolCallNameRepairMiddleware,
    build_skills_backend_factory,
    create_surfsense_compaction_middleware,
    default_skills_sources,
)
from app.agents.new_chat.plugin_loader import (
    PluginContext,
    load_allowed_plugin_names_from_env,
    load_plugin_middlewares,
)
from app.agents.new_chat.tools.registry import BUILTIN_TOOLS
from app.db import ChatVisibility

logger = logging.getLogger(__name__)

# Routing tools with heavy outputs — never prune via context editing when bound.
_SUPERVISOR_PRUNE_PROTECTED: frozenset[str] = frozenset(
    {
        "deliverables",
        "invalid",
        # Align with single-agent surfacing of costly connector reads if names overlap later.
        "read_email",
        "search_emails",
        "generate_report",
        "generate_resume",
        "generate_podcast",
        "generate_video_presentation",
        "generate_image",
    }
)


def _safe_exclude_tools_supervisor(tools: Sequence[BaseTool]) -> tuple[str, ...]:
    enabled = {t.name for t in tools}
    return tuple(n for n in _SUPERVISOR_PRUNE_PROTECTED if n in enabled)


def parse_thread_id_for_action_log(thread_id: int | str | None) -> int | None:
    """Numeric DB thread ids only — UUID strings skip action logging (no FK row)."""
    if thread_id is None:
        return None
    if isinstance(thread_id, int):
        return thread_id
    s = str(thread_id).strip()
    if s.isdigit():
        return int(s)
    return None


def build_supervisor_middleware_stack(
    *,
    llm: BaseChatModel,
    tools: Sequence[BaseTool],
    backend_resolver: Any,
    filesystem_mode: FilesystemMode,
    search_space_id: int,
    user_id: str | None,
    thread_id: int | str | None,
    visibility: ChatVisibility,
    anon_session_id: str | None,
    available_connectors: list[str] | None,
    available_document_types: list[str] | None,
    mentioned_document_ids: list[int] | None,
    max_input_tokens: int | None,
    flags: AgentFeatureFlags | None = None,
) -> list[Any]:
    """Build middleware list for the multi-agent supervisor (parity with ``_build_compiled_agent_blocking`` minus subagents)."""
    flags = flags or get_flags()

    memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    summarization_mw = create_surfsense_compaction_middleware(llm, StateBackend)
    _ = flags.enable_compaction_v2

    context_edit_mw = None
    if (
        flags.enable_context_editing
        and not flags.disable_new_agent_stack
        and max_input_tokens
    ):
        spill_edit = SpillToBackendEdit(
            trigger=int(max_input_tokens * 0.55),
            clear_at_least=int(max_input_tokens * 0.15),
            keep=5,
            exclude_tools=_safe_exclude_tools_supervisor(tools),
            clear_tool_inputs=True,
        )
        clear_edit = ClearToolUsesEdit(
            trigger=int(max_input_tokens * 0.55),
            clear_at_least=int(max_input_tokens * 0.15),
            keep=5,
            exclude_tools=_safe_exclude_tools_supervisor(tools),
            clear_tool_inputs=True,
            placeholder="[cleared - older tool output trimmed for context]",
        )
        context_edit_mw = SpillingContextEditingMiddleware(
            edits=[spill_edit, clear_edit],
            backend_resolver=backend_resolver,
        )

    retry_mw = (
        RetryAfterMiddleware(max_retries=3)
        if flags.enable_retry_after and not flags.disable_new_agent_stack
        else None
    )
    fallback_mw: ModelFallbackMiddleware | None = None
    if flags.enable_model_fallback and not flags.disable_new_agent_stack:
        try:
            fallback_mw = ModelFallbackMiddleware(
                "openai:gpt-4o-mini",
                "anthropic:claude-3-5-haiku-20241022",
            )
        except Exception:
            logger.warning("ModelFallbackMiddleware init failed; skipping.")
            fallback_mw = None
    model_call_limit_mw = (
        ModelCallLimitMiddleware(
            thread_limit=120,
            run_limit=80,
            exit_behavior="end",
        )
        if flags.enable_model_call_limit and not flags.disable_new_agent_stack
        else None
    )
    tool_call_limit_mw = (
        ToolCallLimitMiddleware(
            thread_limit=300, run_limit=80, exit_behavior="continue"
        )
        if flags.enable_tool_call_limit and not flags.disable_new_agent_stack
        else None
    )

    noop_mw = (
        NoopInjectionMiddleware()
        if flags.enable_compaction_v2 and not flags.disable_new_agent_stack
        else None
    )

    repair_mw = None
    if flags.enable_tool_call_repair and not flags.disable_new_agent_stack:
        registered_names: set[str] = {t.name for t in tools}
        registered_names |= {
            "write_todos",
            "ls",
            "read_file",
            "write_file",
            "edit_file",
            "glob",
            "grep",
            "execute",
            # No ``task`` — multi-agent uses routing tools instead of SubAgentMiddleware.
        }
        repair_mw = ToolCallNameRepairMiddleware(
            registered_tool_names=registered_names,
            fuzzy_match_threshold=None,
        )

    doom_loop_mw = (
        DoomLoopMiddleware(threshold=3)
        if flags.enable_doom_loop and not flags.disable_new_agent_stack
        else None
    )

    thread_id_action_log = parse_thread_id_for_action_log(thread_id)
    action_log_mw: ActionLogMiddleware | None = None
    if (
        flags.enable_action_log
        and not flags.disable_new_agent_stack
        and thread_id_action_log is not None
    ):
        try:
            tool_defs_by_name = {td.name: td for td in BUILTIN_TOOLS}
            action_log_mw = ActionLogMiddleware(
                thread_id=thread_id_action_log,
                search_space_id=search_space_id,
                user_id=user_id,
                tool_definitions=tool_defs_by_name,
            )
        except Exception:  # pragma: no cover - defensive
            logger.warning(
                "ActionLogMiddleware init failed; running without it.",
                exc_info=True,
            )
            action_log_mw = None

    busy_mutex_mw: BusyMutexMiddleware | None = (
        BusyMutexMiddleware()
        if flags.enable_busy_mutex and not flags.disable_new_agent_stack
        else None
    )

    otel_mw: OtelSpanMiddleware | None = (
        OtelSpanMiddleware()
        if flags.enable_otel and not flags.disable_new_agent_stack
        else None
    )

    plugin_middlewares: list[Any] = []
    if flags.enable_plugin_loader and not flags.disable_new_agent_stack:
        try:
            allowed_names = load_allowed_plugin_names_from_env()
            if allowed_names:
                plugin_middlewares = load_plugin_middlewares(
                    PluginContext.build(
                        search_space_id=search_space_id,
                        user_id=user_id,
                        thread_visibility=visibility,
                        llm=llm,
                    ),
                    allowed_plugin_names=allowed_names,
                )
        except Exception:  # pragma: no cover - defensive
            logger.warning(
                "Plugin loader failed; continuing without plugins.",
                exc_info=True,
            )
            plugin_middlewares = []

    skills_mw: SkillsMiddleware | None = None
    if flags.enable_skills and not flags.disable_new_agent_stack:
        try:
            skills_factory = build_skills_backend_factory(
                search_space_id=search_space_id
                if filesystem_mode == FilesystemMode.CLOUD
                else None,
            )
            skills_mw = SkillsMiddleware(
                backend=skills_factory,
                sources=default_skills_sources(),
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("SkillsMiddleware init failed; skipping: %s", exc)
            skills_mw = None

    names = {t.name for t in tools}
    selector_mw: LLMToolSelectorMiddleware | None = None
    if (
        flags.enable_llm_tool_selector
        and not flags.disable_new_agent_stack
        and len(tools) > 30
    ):
        try:
            selector_mw = LLMToolSelectorMiddleware(
                model="openai:gpt-4o-mini",
                max_tools=12,
                always_include=[
                    n
                    for n in (
                        "research",
                        "memory",
                        "update_memory",
                        "get_connected_accounts",
                        "scrape_webpage",
                    )
                    if n in names
                ],
            )
        except Exception:
            logger.warning("LLMToolSelectorMiddleware init failed; skipping.")
            selector_mw = None

    deepagent_middleware = [
        busy_mutex_mw,
        otel_mw,
        TodoListMiddleware(),
        memory_middleware,
        AnonymousDocumentMiddleware(anon_session_id=anon_session_id)
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        KnowledgeTreeMiddleware(
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            llm=llm,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        KnowledgePriorityMiddleware(
            llm=llm,
            search_space_id=search_space_id,
            filesystem_mode=filesystem_mode,
            available_connectors=available_connectors,
            available_document_types=available_document_types,
            mentioned_document_ids=mentioned_document_ids,
        ),
        FileIntentMiddleware(llm=llm),
        SurfSenseFilesystemMiddleware(
            backend=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            created_by_id=user_id,
            thread_id=thread_id,
        ),
        KnowledgeBasePersistenceMiddleware(
            search_space_id=search_space_id,
            created_by_id=user_id,
            filesystem_mode=filesystem_mode,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        skills_mw,
        selector_mw,
        model_call_limit_mw,
        tool_call_limit_mw,
        context_edit_mw,
        summarization_mw,
        noop_mw,
        retry_mw,
        fallback_mw,
        repair_mw,
        doom_loop_mw,
        action_log_mw,
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=list(tools)),
        *plugin_middlewares,
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]
    return [m for m in deepagent_middleware if m is not None]
