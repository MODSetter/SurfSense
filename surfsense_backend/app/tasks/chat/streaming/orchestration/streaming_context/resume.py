"""Build ``StreamingContext`` for resume streaming."""

from __future__ import annotations

import logging
import time
from typing import Any

from langgraph.types import Command

from app.agents.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.agents.new_chat.chat_deepagent import create_surfsense_deep_agent
from app.agents.new_chat.checkpointer import get_checkpointer
from app.agents.new_chat.context import SurfSenseContextSchema
from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.agents.new_chat.llm_config import (
    AgentConfig,
    create_chat_litellm_from_agent_config,
    create_chat_litellm_from_config,
    load_agent_config,
    load_global_llm_config_by_id,
)
from app.db import ChatVisibility, SearchSourceConnectorType, async_session_maker
from app.services.auto_model_pin_service import resolve_or_get_pinned_llm_config_id
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.streaming.agent_setup import build_main_agent_for_thread
from app.tasks.chat.streaming.orchestration.input import StreamingContext

logger = logging.getLogger(__name__)


async def build_resume_streaming_context(
    *,
    chat_id: int,
    search_space_id: int,
    decisions: list[dict],
    user_id: str | None = None,
    llm_config_id: int = -1,
    thread_visibility: ChatVisibility | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    disabled_tools: list[str] | None = None,
) -> StreamingContext | None:
    """Build context for ``stream_resume`` execution."""
    session = async_session_maker()
    try:
        llm_config_id = (
            await resolve_or_get_pinned_llm_config_id(
                session,
                thread_id=chat_id,
                search_space_id=search_space_id,
                user_id=user_id,
                selected_llm_config_id=llm_config_id,
            )
        ).resolved_llm_config_id

        llm: Any
        agent_config: AgentConfig | None
        if llm_config_id >= 0:
            agent_config = await load_agent_config(
                session=session,
                config_id=llm_config_id,
                search_space_id=search_space_id,
            )
            if not agent_config:
                logger.warning("resume context build failed: missing config %s", llm_config_id)
                return None
            llm = create_chat_litellm_from_agent_config(agent_config)
        else:
            loaded_llm_config = load_global_llm_config_by_id(llm_config_id)
            if not loaded_llm_config:
                logger.warning(
                    "resume context build failed: missing global config %s",
                    llm_config_id,
                )
                return None
            llm = create_chat_litellm_from_config(loaded_llm_config)
            agent_config = AgentConfig.from_yaml_config(loaded_llm_config)

        connector_service = ConnectorService(session, search_space_id=search_space_id)
        firecrawl_api_key = None
        webcrawler_connector = await connector_service.get_connector_by_type(
            SearchSourceConnectorType.WEBCRAWLER_CONNECTOR,
            search_space_id,
        )
        if webcrawler_connector and webcrawler_connector.config:
            firecrawl_api_key = webcrawler_connector.config.get("FIRECRAWL_API_KEY")

        checkpointer = await get_checkpointer()
        visibility = thread_visibility or ChatVisibility.PRIVATE

        from app.config import config as app_config

        agent_factory = (
            create_multi_agent_chat_deep_agent
            if bool(app_config.MULTI_AGENT_CHAT_ENABLED)
            else create_surfsense_deep_agent
        )
        agent = await build_main_agent_for_thread(
            agent_factory,
            llm=llm,
            search_space_id=search_space_id,
            db_session=session,
            connector_service=connector_service,
            checkpointer=checkpointer,
            user_id=user_id,
            thread_id=chat_id,
            agent_config=agent_config,
            firecrawl_api_key=firecrawl_api_key,
            thread_visibility=visibility,
            filesystem_selection=filesystem_selection,
            disabled_tools=disabled_tools,
        )

        turn_id = f"{chat_id}:{int(time.time() * 1000)}"
        config = {
            "configurable": {
                "thread_id": str(chat_id),
                "request_id": request_id or "unknown",
                "turn_id": turn_id,
                "surfsense_resume_value": {"decisions": decisions},
            },
            "recursion_limit": 10_000,
        }

        runtime_context = SurfSenseContextSchema(
            search_space_id=search_space_id,
            request_id=request_id,
            turn_id=turn_id,
        )

        await session.commit()
        return StreamingContext(
            agent=agent,
            config=config,
            input_data=Command(resume={"decisions": decisions}),
            streaming_service=VercelStreamingService(),
            step_prefix="thinking-resume",
            initial_step_id=None,
            initial_step_title="",
            initial_step_items=None,
            content_builder=None,
            runtime_context=runtime_context,
        )
    except Exception:
        logger.exception(
            "Failed to build resume streaming context (llm_config_id=%s)",
            llm_config_id,
        )
        return None
    finally:
        await session.close()

