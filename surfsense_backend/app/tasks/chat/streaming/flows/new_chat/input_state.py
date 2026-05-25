r"""Assemble the LangGraph ``input_state`` for the new-chat turn.

Pipeline:

  1. **History bootstrap** — only for cloned chats with no LangGraph checkpoint
     yet; flips the per-thread ``needs_history_bootstrap`` flag back to False
     once the rows are loaded.
  2. **Mentioned SurfSense docs** — eager-load chunks so the formatter has the
     full content without a second roundtrip.
  3. **Recent reports** — top 3 by id desc with non-null content, so the LLM
     can resolve ``report_id`` for versioning without spelunking history.
  4. **@-mention resolve** (cloud mode) — substitute ``@title`` tokens in the
     query with canonical ``\`/documents/...\``` paths the LLM expects.
  5. **Context block render** — XML-wrap surfsense docs + reports, prepend to
     the rewritten query, optionally prefix with display name for SEARCH_SPACE
     visibility.
  6. **HumanMessage** — multimodal content if images are attached.

Returns the assembled ``input_state`` dict plus side-channel data the
orchestrator needs downstream (``accepted_folder_ids`` for runtime context;
``mentioned_surfsense_docs`` for the initial thinking step).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.new_chat.filesystem_selection import FilesystemMode
from app.agents.new_chat.mention_resolver import resolve_mentions, substitute_in_text
from app.db import (
    ChatVisibility,
    NewChatThread,
    Report,
    SurfsenseDocsDocument,
)
from app.tasks.chat.streaming.context.mentioned_docs import (
    format_mentioned_surfsense_docs_as_context,
)
from app.utils.content_utils import bootstrap_history_from_db
from app.utils.user_message_multimodal import build_human_message_content

logger = logging.getLogger(__name__)


@dataclass
class NewChatInputState:
    """Everything ``build_new_chat_input_state`` produces.

    ``input_state`` is fed straight to the agent. ``accepted_folder_ids``
    feeds the runtime context (the resolver may have dropped some chips).
    ``mentioned_surfsense_docs`` is consumed by the initial thinking-step
    builder for the FE placeholder before the agent stream starts.
    """

    input_state: dict[str, Any]
    accepted_folder_ids: list[int]
    mentioned_surfsense_docs: list[SurfsenseDocsDocument]


async def build_new_chat_input_state(
    session: AsyncSession,
    *,
    chat_id: int,
    search_space_id: int,
    user_query: str,
    user_image_data_urls: list[str] | None,
    mentioned_document_ids: list[int] | None,
    mentioned_surfsense_doc_ids: list[int] | None,
    mentioned_folder_ids: list[int] | None,
    mentioned_documents: list[dict[str, Any]] | None,
    needs_history_bootstrap: bool,
    thread_visibility: ChatVisibility,
    current_user_display_name: str | None,
    filesystem_mode: str,
    request_id: str | None,
    turn_id: str,
) -> NewChatInputState:
    langchain_messages: list[Any] = []

    if needs_history_bootstrap:
        langchain_messages = await bootstrap_history_from_db(
            session, chat_id, thread_visibility=thread_visibility
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

    # Top 3 reports keyed by id desc (newest first) with content present,
    # surfaced inline so the LLM resolves ``report_id`` for versioning without
    # digging through conversation history.
    recent_reports_result = await session.execute(
        select(Report)
        .filter(
            Report.thread_id == chat_id,
            Report.content.isnot(None),
        )
        .order_by(Report.id.desc())
        .limit(3)
    )
    recent_reports = list(recent_reports_result.scalars().all())

    agent_user_query, accepted_folder_ids = await _resolve_mentions_for_query(
        session,
        search_space_id=search_space_id,
        user_query=user_query,
        filesystem_mode=filesystem_mode,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_surfsense_doc_ids=mentioned_surfsense_doc_ids,
        mentioned_folder_ids=mentioned_folder_ids,
        mentioned_documents=mentioned_documents,
    )

    final_query = _render_query_with_context(
        agent_user_query=agent_user_query,
        mentioned_surfsense_docs=mentioned_surfsense_docs,
        recent_reports=recent_reports,
    )

    if thread_visibility == ChatVisibility.SEARCH_SPACE and current_user_display_name:
        final_query = f"**[{current_user_display_name}]:** {final_query}"

    human_content = build_human_message_content(
        final_query, list(user_image_data_urls or ())
    )
    langchain_messages.append(HumanMessage(content=human_content))

    input_state = {
        "messages": langchain_messages,
        "search_space_id": search_space_id,
        "request_id": request_id or "unknown",
        "turn_id": turn_id,
    }

    return NewChatInputState(
        input_state=input_state,
        accepted_folder_ids=accepted_folder_ids,
        mentioned_surfsense_docs=mentioned_surfsense_docs,
    )


async def _resolve_mentions_for_query(
    session: AsyncSession,
    *,
    search_space_id: int,
    user_query: str,
    filesystem_mode: str,
    mentioned_document_ids: list[int] | None,
    mentioned_surfsense_doc_ids: list[int] | None,
    mentioned_folder_ids: list[int] | None,
    mentioned_documents: list[dict[str, Any]] | None,
) -> tuple[str, list[int]]:
    r"""Resolve @-mention chips and rewrite the user query to canonical paths.

    Cloud mode only: local-folder mode keeps the legacy ``@title`` text path
    (mention support there is a follow-up task — the path scheme is
    mount-rooted and the picker UI both need separate work).

    The substitution lands in the returned ``agent_user_query`` ONLY — the
    original ``user_query`` (with ``@title`` tokens) flows untouched into
    ``persist_user_turn`` so chip rendering on reload still works
    (``UserTextPart`` → ``parseMentionSegments`` matches ``@title``, not
    ``\`/documents/...\```). It also feeds the human-readable surfaces — SSE
    "Processing X" status, auto thread title, memory seed — which all want
    what the user typed.
    """
    agent_user_query = user_query
    accepted_folder_ids: list[int] = []

    has_any_mention = bool(
        mentioned_document_ids
        or mentioned_surfsense_doc_ids
        or mentioned_folder_ids
        or mentioned_documents
    )
    if filesystem_mode != FilesystemMode.CLOUD.value or not has_any_mention:
        return agent_user_query, accepted_folder_ids

    from app.schemas.new_chat import MentionedDocumentInfo

    chip_objs: list[MentionedDocumentInfo] | None = None
    if mentioned_documents:
        chip_objs = []
        for raw in mentioned_documents:
            if isinstance(raw, MentionedDocumentInfo):
                chip_objs.append(raw)
                continue
            try:
                chip_objs.append(MentionedDocumentInfo.model_validate(raw))
            except Exception:
                logger.debug(
                    "stream_new_chat: dropping malformed mention chip %r", raw
                )

    resolved = await resolve_mentions(
        session,
        search_space_id=search_space_id,
        mentioned_documents=chip_objs,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_surfsense_doc_ids=mentioned_surfsense_doc_ids,
        mentioned_folder_ids=mentioned_folder_ids,
    )
    agent_user_query = substitute_in_text(user_query, resolved.token_to_path)
    accepted_folder_ids = resolved.mentioned_folder_ids
    return agent_user_query, accepted_folder_ids


def _render_query_with_context(
    *,
    agent_user_query: str,
    mentioned_surfsense_docs: list[SurfsenseDocsDocument],
    recent_reports: list[Report],
) -> str:
    """Prepend surfsense-docs + recent-reports XML blocks to the user query."""
    context_parts: list[str] = []

    if mentioned_surfsense_docs:
        context_parts.append(
            format_mentioned_surfsense_docs_as_context(mentioned_surfsense_docs)
        )

    if recent_reports:
        report_lines: list[str] = []
        for r in recent_reports:
            report_lines.append(
                f'  - report_id={r.id}, title="{r.title}", '
                f'style="{r.report_style or "detailed"}"'
            )
        reports_listing = "\n".join(report_lines)
        context_parts.append(
            "<report_context>\n"
            "Previously generated reports in this conversation:\n"
            f"{reports_listing}\n\n"
            "If the user wants to MODIFY, REVISE, UPDATE, or ADD to one of "
            "these reports, set parent_report_id to the relevant report_id above.\n"
            "If the user wants a completely NEW report on a different topic, "
            "leave parent_report_id unset.\n"
            "</report_context>"
        )

    if context_parts:
        context = "\n\n".join(context_parts)
        return f"{context}\n\n<user_query>{agent_user_query}</user_query>"

    return agent_user_query
