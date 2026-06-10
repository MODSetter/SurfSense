"""Single per-thread agent (re)build path.

A graph swap mid-turn would corrupt checkpointer state for the same
``thread_id``, so both the initial build and any mid-stream 429 recovery rebuild
must funnel through this single function.
"""

from __future__ import annotations

from typing import Any

from app.agents.chat.multi_agent_chat.shared.filesystem_selection import (
    FilesystemSelection,
)
from app.agents.chat.runtime.llm_config import AgentConfig
from app.db import ChatVisibility
from app.services.connector_service import ConnectorService


async def build_main_agent_for_thread(
    agent_factory: Any,
    *,
    llm: Any,
    search_space_id: int,
    db_session: Any,
    connector_service: ConnectorService,
    checkpointer: Any,
    user_id: str | None,
    thread_id: int | None,
    agent_config: AgentConfig | None,
    firecrawl_api_key: str | None,
    thread_visibility: ChatVisibility | None,
    filesystem_selection: FilesystemSelection | None,
    disabled_tools: list[str] | None = None,
    mentioned_document_ids: list[int] | None = None,
) -> Any:
    return await agent_factory(
        llm=llm,
        search_space_id=search_space_id,
        db_session=db_session,
        connector_service=connector_service,
        checkpointer=checkpointer,
        user_id=user_id,
        thread_id=thread_id,
        agent_config=agent_config,
        firecrawl_api_key=firecrawl_api_key,
        thread_visibility=thread_visibility,
        filesystem_selection=filesystem_selection,
        disabled_tools=disabled_tools,
        mentioned_document_ids=mentioned_document_ids,
    )
