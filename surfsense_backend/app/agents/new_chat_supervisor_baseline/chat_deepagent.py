"""
Supervisor baseline: **no registry tools** and **no tool-injecting middleware**
(no ``task`` / subagents, filesystem, todos, skills, permission, pruning, repair, …).

Connector/document discovery still feeds :class:`KnowledgePriorityMiddleware` so turns
can include KB priority hints.

System prompt: :func:`build_supervisor_system_prompt` — SurfSense ``agent_*`` identity
fragments plus supervisor-scoped KB/memory text and composer citation/provider blocks,
without tool lists or ``tool_routing`` (see module docstring there).

See :mod:`app.agents.new_chat.chat_deepagent` for the full production agent.

Implementation: :mod:`app.agents.new_chat_supervisor_baseline.deep_agent`.
"""

import asyncio
import logging
import time
from collections.abc import Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.types import Checkpointer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.feature_flags import AgentFeatureFlags, get_flags
from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.agents.new_chat.llm_config import AgentConfig
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService
from app.utils.perf import get_perf_logger

from app.agents.new_chat_supervisor_baseline.deep_agent.compiled_agent import (
    build_compiled_agent_blocking,
)
from app.agents.new_chat_supervisor_baseline.deep_agent.connector_searchable import (
    map_connectors_to_searchable_types,
)
from app.agents.new_chat_supervisor_baseline.supervisor_system_prompt import (
    build_supervisor_system_prompt,
)

_perf_log = get_perf_logger()


async def create_surfsense_deep_agent(
    llm: BaseChatModel,
    search_space_id: int,
    db_session: AsyncSession,
    connector_service: ConnectorService,
    checkpointer: Checkpointer,
    user_id: str | None = None,
    thread_id: int | None = None,
    agent_config: AgentConfig | None = None,
    enabled_tools: list[str] | None = None,
    disabled_tools: list[str] | None = None,
    additional_tools: Sequence[BaseTool] | None = None,
    firecrawl_api_key: str | None = None,
    thread_visibility: ChatVisibility | None = None,
    mentioned_document_ids: list[int] | None = None,
    anon_session_id: str | None = None,
    filesystem_selection: FilesystemSelection | None = None,
):
    """
    Build the supervisor baseline agent: registry tools are not loaded.

    Parameters such as ``enabled_tools``, ``additional_tools``, and ``firecrawl_api_key``
    are ignored for now; kept so call sites stay compatible.
    """
    _ = (enabled_tools, disabled_tools, additional_tools, firecrawl_api_key, db_session)

    _t_agent_total = time.perf_counter()

    filesystem_selection = filesystem_selection or FilesystemSelection()
    _fs_mode = filesystem_selection.mode

    available_connectors: list[str] | None = None
    available_document_types: list[str] | None = None

    _t0 = time.perf_counter()
    try:
        connector_types = await connector_service.get_available_connectors(
            search_space_id
        )
        if connector_types:
            available_connectors = map_connectors_to_searchable_types(connector_types)

        available_document_types = await connector_service.get_available_document_types(
            search_space_id
        )

    except Exception as e:
        logging.warning(f"Failed to discover available connectors/document types: {e}")
    _perf_log.info(
        "[create_agent] Connector/doc-type discovery in %.3fs",
        time.perf_counter() - _t0,
    )

    visibility = thread_visibility or ChatVisibility.PRIVATE

    tools: list[BaseTool] = []

    _flags: AgentFeatureFlags = get_flags()
    _perf_log.info("[create_agent] supervisor baseline: 0 registry tools")

    _t0 = time.perf_counter()

    final_system_prompt = build_supervisor_system_prompt(
        agent_config=agent_config,
        thread_visibility=thread_visibility,
        llm=llm,
    )
    _perf_log.info(
        "[create_agent] System prompt built in %.3fs", time.perf_counter() - _t0
    )

    _t0 = time.perf_counter()
    agent = await asyncio.to_thread(
        build_compiled_agent_blocking,
        llm=llm,
        tools=tools,
        final_system_prompt=final_system_prompt,
        filesystem_mode=_fs_mode,
        search_space_id=search_space_id,
        user_id=user_id,
        thread_id=thread_id,
        visibility=visibility,
        anon_session_id=anon_session_id,
        available_connectors=available_connectors,
        available_document_types=available_document_types,
        mentioned_document_ids=mentioned_document_ids,
        flags=_flags,
        checkpointer=checkpointer,
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
