"""Assemble the main-agent deep-agent middleware list (LangChain + SurfSense + deepagents)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from deepagents import SubAgent
from deepagents.backends import StateBackend
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT
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
from langgraph.types import Checkpointer

from ...context_prune.prune_tool_names import safe_exclude_tools
from app.agents.multi_agent_with_deepagents.subagents import (
    build_subagents,
    get_subagents_to_exclude,
)
from app.agents.multi_agent_with_deepagents.subagents.shared.permissions import (
    ToolsPermissions,
)
from app.agents.new_chat.feature_flags import AgentFeatureFlags
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
    PermissionMiddleware,
    RetryAfterMiddleware,
    SpillingContextEditingMiddleware,
    SpillToBackendEdit,
    SurfSenseFilesystemMiddleware,
    ToolCallNameRepairMiddleware,
    build_skills_backend_factory,
    create_surfsense_compaction_middleware,
    default_skills_sources,
)
from app.agents.new_chat.permissions import Rule, Ruleset
from app.agents.new_chat.plugin_loader import (
    PluginContext,
    load_allowed_plugin_names_from_env,
    load_plugin_middlewares,
)
from app.agents.new_chat.tools.registry import BUILTIN_TOOLS
from app.db import ChatVisibility

from .checkpointed_subagent_middleware import SurfSenseCheckpointedSubAgentMiddleware


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
    """Build ordered middleware for ``create_agent`` (Nones already stripped)."""
    _memory_middleware = MemoryInjectionMiddleware(
        user_id=user_id,
        search_space_id=search_space_id,
        thread_visibility=visibility,
    )

    gp_middleware = [
        TodoListMiddleware(),
        _memory_middleware,
        FileIntentMiddleware(llm=llm),
        SurfSenseFilesystemMiddleware(
            backend=backend_resolver,
            filesystem_mode=filesystem_mode,
            search_space_id=search_space_id,
            created_by_id=user_id,
            thread_id=thread_id,
        ),
        create_surfsense_compaction_middleware(llm, StateBackend),
        PatchToolCallsMiddleware(),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]

    # Build permission rulesets up front so the GP subagent can mirror ``ask``
    # rules into ``interrupt_on``: tool calls emitted from within ``task`` runs
    # never reach the parent's ``PermissionMiddleware``.
    is_desktop_fs = filesystem_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER
    permission_enabled = flags.enable_permission and not flags.disable_new_agent_stack
    permission_rulesets: list[Ruleset] = []
    if permission_enabled or is_desktop_fs:
        permission_rulesets.append(
            Ruleset(
                rules=[Rule(permission="*", pattern="*", action="allow")],
                origin="surfsense_defaults",
            )
        )
        if is_desktop_fs:
            permission_rulesets.append(
                Ruleset(
                    rules=[
                        Rule(permission="rm", pattern="*", action="ask"),
                        Rule(permission="rmdir", pattern="*", action="ask"),
                        Rule(permission="move_file", pattern="*", action="ask"),
                        Rule(permission="edit_file", pattern="*", action="ask"),
                        Rule(permission="write_file", pattern="*", action="ask"),
                    ],
                    origin="desktop_safety",
                )
            )

    # Tools that self-prompt via ``request_approval`` must not also appear
    # as ``ask`` rules — that would double-prompt the user for one call.
    _tool_names_in_use = {t.name for t in tools}

    # Deny parent-bound tools whose ``required_connector`` is missing.
    # No-op today (connector subagents are pruned upstream); guards future
    # additions to the parent's tool list.
    if permission_enabled:
        _available_set = set(available_connectors or [])
        _synthesized: list[Rule] = []
        for tool_def in BUILTIN_TOOLS:
            if tool_def.name not in _tool_names_in_use:
                continue
            rc = tool_def.required_connector
            if rc and rc not in _available_set:
                _synthesized.append(
                    Rule(permission=tool_def.name, pattern="*", action="deny")
                )
        if _synthesized:
            permission_rulesets.append(
                Ruleset(rules=_synthesized, origin="connector_synthesized")
            )
    gp_interrupt_on: dict[str, bool] = {
        rule.permission: True
        for rs in permission_rulesets
        for rule in rs.rules
        if rule.action == "ask" and rule.permission in _tool_names_in_use
    }

    general_purpose_spec: SubAgent = {  # type: ignore[typeddict-unknown-key]
        **GENERAL_PURPOSE_SUBAGENT,
        "model": llm,
        "tools": tools,
        "middleware": gp_middleware,
    }
    if gp_interrupt_on:
        general_purpose_spec["interrupt_on"] = gp_interrupt_on

    # Deny-only on subagents: ``task`` runs bypass the parent's
    # PermissionMiddleware, while bucket-based ask gates own the ask path.
    subagent_deny_rulesets: list[Ruleset] = [
        Ruleset(
            rules=[r for r in rs.rules if r.action == "deny"],
            origin=rs.origin,
        )
        for rs in permission_rulesets
    ]
    subagent_deny_rulesets = [rs for rs in subagent_deny_rulesets if rs.rules]

    subagent_deny_permission_mw: PermissionMiddleware | None = (
        PermissionMiddleware(rulesets=subagent_deny_rulesets)
        if subagent_deny_rulesets
        else None
    )

    if subagent_deny_permission_mw is not None:
        # Run deny check on already-repaired tool calls; insert before
        # PatchToolCallsMiddleware (append if the slot moves).
        _patch_idx = next(
            (
                i
                for i, m in enumerate(gp_middleware)
                if isinstance(m, PatchToolCallsMiddleware)
            ),
            len(gp_middleware),
        )
        gp_middleware.insert(_patch_idx, subagent_deny_permission_mw)

    registry_subagents: list[SubAgent] = []
    try:
        subagent_extra_middleware: list[Any] = [
            TodoListMiddleware(),
            SurfSenseFilesystemMiddleware(
                backend=backend_resolver,
                filesystem_mode=filesystem_mode,
                search_space_id=search_space_id,
                created_by_id=user_id,
                thread_id=thread_id,
            ),
        ]
        if subagent_deny_permission_mw is not None:
            subagent_extra_middleware.append(subagent_deny_permission_mw)
        registry_subagents = build_subagents(
            dependencies=subagent_dependencies,
            model=llm,
            extra_middleware=subagent_extra_middleware,
            mcp_tools_by_agent=mcp_tools_by_agent or {},
            exclude=get_subagents_to_exclude(available_connectors),
            disabled_tools=disabled_tools,
        )
        logging.info(
            "Registry subagents: %s",
            [s["name"] for s in registry_subagents],
        )
    except Exception as exc:
        logging.warning("Registry subagent build failed: %s", exc)
        registry_subagents = []

    subagent_specs: list[SubAgent] = [general_purpose_spec, *registry_subagents]

    summarization_mw = create_surfsense_compaction_middleware(llm, StateBackend)

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
            exclude_tools=safe_exclude_tools(tools),
            clear_tool_inputs=True,
        )
        clear_edit = ClearToolUsesEdit(
            trigger=int(max_input_tokens * 0.55),
            clear_at_least=int(max_input_tokens * 0.15),
            keep=5,
            exclude_tools=safe_exclude_tools(tools),
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
            logging.warning("ModelFallbackMiddleware init failed; skipping.")
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
            "task",
            "mkdir",
            "cd",
            "pwd",
            "move_file",
            "rm",
            "rmdir",
            "list_tree",
            "execute_code",
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

    permission_mw: PermissionMiddleware | None = (
        PermissionMiddleware(rulesets=permission_rulesets)
        if permission_rulesets
        else None
    )

    action_log_mw: ActionLogMiddleware | None = None
    if (
        flags.enable_action_log
        and not flags.disable_new_agent_stack
        and thread_id is not None
    ):
        try:
            tool_defs_by_name = {td.name: td for td in BUILTIN_TOOLS}
            action_log_mw = ActionLogMiddleware(
                thread_id=thread_id,
                search_space_id=search_space_id,
                user_id=user_id,
                tool_definitions=tool_defs_by_name,
            )
        except Exception:  # pragma: no cover - defensive
            logging.warning(
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
            logging.warning(
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
            logging.warning("SkillsMiddleware init failed; skipping: %s", exc)
            skills_mw = None

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
                    name
                    for name in (
                        "update_memory",
                        "get_connected_accounts",
                        "scrape_webpage",
                    )
                    if name in {t.name for t in tools}
                ],
            )
        except Exception:
            logging.warning("LLMToolSelectorMiddleware init failed; skipping.")
            selector_mw = None

    deepagent_middleware = [
        busy_mutex_mw,
        otel_mw,
        TodoListMiddleware(),
        _memory_middleware,
        AnonymousDocumentMiddleware(
            anon_session_id=anon_session_id,
        )
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
            thread_id=thread_id,
        )
        if filesystem_mode == FilesystemMode.CLOUD
        else None,
        skills_mw,
        SurfSenseCheckpointedSubAgentMiddleware(
            checkpointer=checkpointer,
            backend=StateBackend,
            subagents=subagent_specs,
        ),
        selector_mw,
        model_call_limit_mw,
        tool_call_limit_mw,
        context_edit_mw,
        summarization_mw,
        noop_mw,
        retry_mw,
        fallback_mw,
        repair_mw,
        permission_mw,
        doom_loop_mw,
        action_log_mw,
        PatchToolCallsMiddleware(),
        DedupHITLToolCallsMiddleware(agent_tools=list(tools)),
        *plugin_middlewares,
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
    ]
    return [m for m in deepagent_middleware if m is not None]
