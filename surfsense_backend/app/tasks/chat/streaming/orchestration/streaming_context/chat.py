"""Build ``StreamingContext`` for chat streaming."""

from __future__ import annotations

import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

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
from app.db import (
    ChatVisibility,
    NewChatThread,
    Report,
    SearchSourceConnectorType,
    SurfsenseDocsDocument,
    async_session_maker,
)
from app.services.auto_model_pin_service import resolve_or_get_pinned_llm_config_id
from app.services.connector_service import ConnectorService
from app.services.new_streaming_service import VercelStreamingService
from app.tasks.chat.stream_new_chat import format_mentioned_surfsense_docs_as_context
from app.tasks.chat.streaming.agent_setup import build_main_agent_for_thread
from app.tasks.chat.streaming.orchestration.input import StreamingContext
from app.utils.content_utils import bootstrap_history_from_db
from app.utils.user_message_multimodal import build_human_message_content

logger = logging.getLogger(__name__)


async def build_chat_streaming_context(
    *,
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    user_image_data_urls: list[str] | None = None,
) -> StreamingContext | None:
    """Build context for ``stream_output`` from route-level chat inputs."""
    session = async_session_maker()
    try:
        requested_llm_config_id = llm_config_id
        llm_config_id = (
            await resolve_or_get_pinned_llm_config_id(
                session,
                thread_id=chat_id,
                search_space_id=search_space_id,
                user_id=user_id,
                selected_llm_config_id=llm_config_id,
                requires_image_input=bool(user_image_data_urls),
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
                logger.warning("streaming context build failed: missing config %s", llm_config_id)
                return None
            llm = create_chat_litellm_from_agent_config(agent_config)
        else:
            loaded_llm_config = load_global_llm_config_by_id(llm_config_id)
            if not loaded_llm_config:
                logger.warning(
                    "streaming context build failed: missing global config %s",
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
            mentioned_document_ids=mentioned_document_ids,
        )

        langchain_messages = []
        if needs_history_bootstrap:
            langchain_messages = await bootstrap_history_from_db(
                session,
                chat_id,
                thread_visibility=visibility,
            )
            thread_result = await session.execute(
                select(NewChatThread).filter(NewChatThread.id == chat_id)
            )
            thread = thread_result.scalars().first()
            if thread:
                thread.needs_history_bootstrap = False
                await session.commit()

        mentioned_surfsense_docs: list[SurfsenseDocsDocument] = []
        if mentioned_surfsense_doc_ids:
            result = await session.execute(
                select(SurfsenseDocsDocument)
                .options(selectinload(SurfsenseDocsDocument.chunks))
                .filter(SurfsenseDocsDocument.id.in_(mentioned_surfsense_doc_ids))
            )
            mentioned_surfsense_docs = list(result.scalars().all())

        recent_reports_result = await session.execute(
            select(Report)
            .filter(Report.thread_id == chat_id, Report.content.isnot(None))
            .order_by(Report.id.desc())
            .limit(3)
        )
        recent_reports = list(recent_reports_result.scalars().all())

        final_query = user_query
        context_parts = []
        if mentioned_surfsense_docs:
            context_parts.append(
                format_mentioned_surfsense_docs_as_context(mentioned_surfsense_docs)
            )
        if recent_reports:
            report_lines = [
                f'  - report_id={r.id}, title="{r.title}", style="{r.report_style or "detailed"}"'
                for r in recent_reports
            ]
            reports_listing = "\n".join(report_lines)
            context_parts.append(
                "<report_context>\n"
                "Previously generated reports in this conversation:\n"
                f"{reports_listing}\n\n"
                "If the user wants to MODIFY, REVISE, UPDATE, or ADD to one of these reports, "
                "set parent_report_id to the relevant report_id above.\n"
                "If the user wants a completely NEW report on a different topic, "
                "leave parent_report_id unset.\n"
                "</report_context>"
            )
        if context_parts:
            joined_context = "\n\n".join(context_parts)
            final_query = f"{joined_context}\n\n<user_query>{user_query}</user_query>"
        if visibility == ChatVisibility.SEARCH_SPACE and current_user_display_name:
            final_query = f"**[{current_user_display_name}]:** {final_query}"

        human_content = build_human_message_content(
            final_query,
            list(user_image_data_urls or ()),
        )
        langchain_messages.append(HumanMessage(content=human_content))

        turn_id = f"{chat_id}:{int(time.time() * 1000)}"
        input_state = {
            "messages": langchain_messages,
            "search_space_id": search_space_id,
            "request_id": request_id or "unknown",
            "turn_id": turn_id,
        }
        configurable = {
            "thread_id": str(chat_id),
            "request_id": request_id or "unknown",
            "turn_id": turn_id,
        }
        if checkpoint_id:
            configurable["checkpoint_id"] = checkpoint_id
        config = {"configurable": configurable, "recursion_limit": 10_000}

        initial_title = (
            "Analyzing referenced content"
            if mentioned_surfsense_docs
            else "Understanding your request"
        )
        action_verb = "Analyzing" if mentioned_surfsense_docs else "Processing"
        query_excerpt = user_query[:80] + ("..." if len(user_query) > 80 else "")
        query_part = query_excerpt if query_excerpt.strip() else "(message)"
        initial_items = [f"{action_verb}: {query_part}"]

        runtime_context = SurfSenseContextSchema(
            search_space_id=search_space_id,
            mentioned_document_ids=list(mentioned_document_ids or []),
            request_id=request_id,
            turn_id=turn_id,
        )

        await session.commit()
        return StreamingContext(
            agent=agent,
            config=config,
            input_data=input_state,
            streaming_service=VercelStreamingService(),
            step_prefix="thinking",
            initial_step_id="thinking-1",
            initial_step_title=initial_title,
            initial_step_items=initial_items,
            content_builder=None,
            runtime_context=runtime_context,
        )
    except Exception:
        logger.exception(
            "Failed to build chat streaming context (llm_config_id=%s requested=%s)",
            llm_config_id,
            requested_llm_config_id,
        )
        return None
    finally:
        await session.close()

