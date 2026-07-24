"""Async factory: tools, system prompt, MCP buckets for subagents, then sync graph compile."""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat.shared.feature_flags import (
    AgentFeatureFlags,
    get_flags,
)
from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemMode,
    FilesystemSelection,
)
from app.agents.chat.multi_agent_chat.shared.middleware.filesystem.backends.resolver import (
    build_backend_resolver,
)
from app.agents.chat.multi_agent_chat.subagents import (
    get_subagents_to_exclude,
    main_prompt_registry_subagent_lines,
)
from app.agents.chat.multi_agent_chat.subagents.mcp_tools.index import (
    load_mcp_tools_by_connector,
)
from app.agents.chat.runtime.llm_config import AgentConfig
from app.agents.chat.runtime.prompt_caching import (
    apply_litellm_prompt_caching,
)
from app.auth.context import AuthContext
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.services.user_tool_allowlist import (
    fetch_user_allowlist_rulesets,
    make_trusted_tool_saver,
)
from app.utils.perf import get_perf_logger

from ..system_prompt import build_main_agent_system_prompt
from ..tools import (
    MAIN_AGENT_SURFSENSE_TOOL_NAMES,
    MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED,
)
from ..tools.invalid_tool import INVALID_TOOL_NAME, invalid_tool
from ..tools.registry import build_main_agent_tools
from .agent_cache import build_agent_with_cache
from .connector_searchable_types import map_connectors_to_searchable_types

_perf_log = get_perf_logger()


async def create_multi_agent_chat_deep_agent(
    llm: BaseChatModel,
    workspace_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    checkpointer: Checkpointer,
    user_id: str | None = None,
    thread_id: int | None = None,
    agent_config: AgentConfig | None = None,
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
    thread_visibility: ChatVisibility | None = None,
    mentioned_document_ids: list[int] | None = None,
    anon_session_id: str | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    image_gen_model_id: int | None = None,
    auth_context: AuthContext | None = None,
):
    """Deep agent with SurfSense tools/middleware; registry route subagents behind ``task`` when enabled.

    ``image_gen_model_id`` overrides the workspace's image model for
    this invocation (used by automations to run on their captured model). When
    ``None``, the ``generate_image`` tool resolves the live workspace pref.
    """
    _t_agent_total = time.perf_counter()

    apply_litellm_prompt_caching(llm, agent_config=agent_config, thread_id=thread_id)

    filesystem_selection = filesystem_selection or FilesystemSelection()
    backend_resolver = build_backend_resolver(
        filesystem_selection,
        workspace_id=workspace_id
        if filesystem_selection.mode == FilesystemMode.CLOUD
        else None,
    )

    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        connector_types = await connector_service.get_available_connectors(workspace_id)
        available_connectors = map_connectors_to_searchable_types(connector_types)

        available_document_types = await connector_service.get_available_document_types(
            workspace_id
        )

    except Exception as e:
        logging.warning(
            "Connector/doc-type discovery failed; excluding connector subagents this turn: %s",
            e,
        )

    # Fail closed: a None list short-circuits ``get_subagents_to_exclude`` to "exclude
    # nothing", which would silently advertise every connector specialist on a flaky
    # discovery call. Empty list excludes connector-gated subagents while keeping builtins.
    if available_connectors is None:
        available_connectors = []
    if available_document_types is None:
        available_document_types = []
    _perf_log.info(
        "[create_agent] Connector/doc-type discovery in %.3fs",
        time.perf_counter() - _t0,
    )

    visibility = thread_visibility or ChatVisibility.PRIVATE

    _model_profile = getattr(llm, "profile", None)
    _max_input_tokens: int | None = (
        _model_profile.get("max_input_tokens")
        if isinstance(_model_profile, dict)
        else None
    )

    dependencies: dict[str, Any] = {
        "workspace_id": workspace_id,
        "db_session": db_session,
        "connector_service": connector_service,
        "user_id": user_id,
        "auth_context": auth_context,
        "thread_id": thread_id,
        "thread_visibility": visibility,
        "available_connectors": available_connectors,
        "available_document_types": available_document_types,
        "max_input_tokens": _max_input_tokens,
        "llm": llm,
        # Per-invocation image model override (automations run on their captured
        # model). Reaches the generate_image subagent tool via subagent_dependencies.
        "image_gen_model_id_override": image_gen_model_id,
    }

    _t0 = time.perf_counter()
    try:
        mcp_tools_by_agent = await load_mcp_tools_by_connector(db_session, workspace_id)
    except Exception as e:
        # Degrade to builtins-only rather than aborting the turn: a transient
        # DB or MCP-server hiccup should not deny the user a response.
        logging.warning(
            "MCP tool discovery failed; subagents will run without MCP tools this turn: %s",
            e,
        )
        mcp_tools_by_agent = {}
    _perf_log.info(
        "[create_agent] load_mcp_tools_by_connector in %.3fs (%d agents)",
        time.perf_counter() - _t0,
        len(mcp_tools_by_agent),
    )

    # User-scoped allow-list ("Always Allow" persisted to
    # ``SearchSourceConnector.config.trusted_tools``). Layered last in each
    # subagent's PermissionMiddleware so user ``allow`` overrides coded
    # ``ask`` via last-match-wins. Anonymous turns and read failures both
    # degrade to "no user rules" rather than blocking the turn.
    user_allowlist_by_subagent: dict[str, Any] = {}
    trusted_tool_saver = None
    if user_id:
        try:
            import uuid as _uuid

            user_uuid = _uuid.UUID(user_id)
        except (TypeError, ValueError):
            user_uuid = None

        if user_uuid is not None:
            _t0 = time.perf_counter()
            try:
                user_allowlist_by_subagent = await fetch_user_allowlist_rulesets(
                    db_session,
                    user_id=user_uuid,
                    workspace_id=workspace_id,
                )
            except Exception as e:
                logging.warning(
                    "User allow-list fetch failed; subagents will run without user trust rules this turn: %s",
                    e,
                )
                user_allowlist_by_subagent = {}
            _perf_log.info(
                "[create_agent] fetch_user_allowlist_rulesets in %.3fs (%d subagents have rules)",
                time.perf_counter() - _t0,
                len(user_allowlist_by_subagent),
            )
            trusted_tool_saver = make_trusted_tool_saver(user_uuid)
    dependencies["user_allowlist_by_subagent"] = user_allowlist_by_subagent
    dependencies["trusted_tool_saver"] = trusted_tool_saver

    modified_disabled_tools = list(disabled_tools) if disabled_tools else []

    if enabled_tools is not None:
        main_agent_enabled_tools = [
            n for n in enabled_tools if n in MAIN_AGENT_SURFSENSE_TOOL_NAMES
        ]
    else:
        main_agent_enabled_tools = list(MAIN_AGENT_SURFSENSE_TOOL_NAMES_ORDERED)

    _t0 = time.perf_counter()
    # Main agent builds only its own small SurfSense toolset via the SRP
    # main-agent registry; connectors/MCP/deliverables are delegated to
    # subagents, so no MCP loading or connector construction happens here.
    tools = build_main_agent_tools(
        dependencies=dependencies,
        enabled_tools=main_agent_enabled_tools,
        disabled_tools=modified_disabled_tools,
        additional_tools=list(additional_tools) if additional_tools else None,
    )

    # Read-only exception to the "main agent is a pure router" stance: the
    # context-editing spill placeholder points at read_run/search_run, so the
    # main agent needs those tools to follow it. See middleware/stack.py.
    from app.agents.chat.multi_agent_chat.subagents.shared.run_reader import (
        build_run_reader_tools,
    )

    tools = [*list(tools), *build_run_reader_tools(workspace_id=workspace_id)]

    _flags: AgentFeatureFlags = get_flags()
    if _flags.enable_tool_call_repair and INVALID_TOOL_NAME not in {
        t.name for t in tools
    }:
        tools = [*list(tools), invalid_tool]
    _perf_log.info(
        "[create_agent] build_tools_async in %.3fs (%d tools)",
        time.perf_counter() - _t0,
        len(tools),
    )

    _t0 = time.perf_counter()
    _enabled_tool_names = {t.name for t in tools}
    _user_disabled_tool_names = set(disabled_tools) if disabled_tools else set()

    _model_name: str | None = None
    prof = getattr(llm, "model_name", None) or getattr(llm, "model", None)
    if isinstance(prof, str):
        _model_name = prof

    _connector_exclude = get_subagents_to_exclude(available_connectors)
    _registry_subagent_prompt_lines = main_prompt_registry_subagent_lines(
        _connector_exclude
    )

    if agent_config is not None:
        system_prompt = build_main_agent_system_prompt(
            today=None,
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            custom_system_instructions=agent_config.system_instructions,
            use_default_system_instructions=agent_config.use_default_system_instructions,
            citations_enabled=agent_config.citations_enabled,
            model_name=_model_name or getattr(agent_config, "model_name", None),
            registry_subagent_prompt_lines=_registry_subagent_prompt_lines,
        )
    else:
        system_prompt = build_main_agent_system_prompt(
            thread_visibility=thread_visibility,
            enabled_tool_names=_enabled_tool_names,
            disabled_tool_names=_user_disabled_tool_names,
            citations_enabled=True,
            model_name=_model_name,
            registry_subagent_prompt_lines=_registry_subagent_prompt_lines,
        )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    final_system_prompt = system_prompt

    config_id = agent_config.config_id if agent_config is not None else None

    _t0 = time.perf_counter()
    agent = await build_agent_with_cache(
        llm=llm,
        tools=tools,
        final_system_prompt=final_system_prompt,
        backend_resolver=backend_resolver,
        filesystem_mode=filesystem_selection.mode,
        workspace_id=workspace_id,
        user_id=user_id,
        thread_id=thread_id,
        visibility=visibility,
        anon_session_id=anon_session_id,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        mentioned_document_ids=mentioned_document_ids,
        max_input_tokens=_max_input_tokens,
        flags=_flags,
        checkpointer=checkpointer,
        subagent_dependencies=dependencies,
        mcp_tools_by_agent=mcp_tools_by_agent,
        disabled_tools=disabled_tools,
        config_id=config_id,
        image_gen_model_id_override=image_gen_model_id,
    )
    _perf_log.info(
        "[create_agent] Middleware stack + graph compiled in %.3fs",
        time.perf_counter() - _t0,
    )

    _perf_log.info(
        "[create_agent] Total agent creation in %.3fs",
        time.perf_counter() - _t_agent_total,
    )
    return agent
