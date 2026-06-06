"""Run one ``agent_task`` invocation: ainvoke + auto-decision resume loop."""

from __future__ import annotations

import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat.multi_agent_chat import create_multi_agent_chat_deep_agent
from app.agents.chat.runtime.mention_resolver import (
    resolve_mentions,
    substitute_in_text,
)
from app.agents.chat.shared.context import SurfSenseContextSchema
from app.db import ChatVisibility, async_session_maker
from app.schemas.new_chat import MentionedDocumentInfo

from ...types import ActionContext
from .auto_decide import build_auto_decisions
from .dependencies import build_dependencies
from .finalize import extract_final_assistant_message

# Cap on HITL resume iterations. The agent should not need this many turns in one
# step; treat overshoot as a runaway and fail the step.
_MAX_RESUMES = 50


def _build_connector_block(connectors: list[dict[str, Any]]) -> str | None:
    """Render the ``<mentioned_connectors>`` context block (same shape as chat).

    Mirrors ``stream_new_chat`` so the agent gets the exact connector accounts
    the user picked. Returns ``None`` when nothing renders.
    """
    lines: list[str] = []
    for connector in connectors:
        connector_id = connector.get("id")
        connector_type = connector.get("connector_type") or connector.get(
            "document_type"
        )
        account_name = connector.get("account_name") or connector.get("title")
        if connector_id is None or connector_type is None:
            continue
        lines.append(
            f'  - connector_id={connector_id}, connector_type="{connector_type}", '
            f'account_name="{account_name or ""}"'
        )
    if not lines:
        return None
    return (
        "<mentioned_connectors>\n"
        "The user selected these exact connector accounts with @. "
        "These entries are selection metadata, not retrieved connector content. "
        "When a connector-backed tool needs an account, use the matching "
        "connector_id from this list if the tool supports connector_id:\n"
        + "\n".join(lines)
        + "\n</mentioned_connectors>"
    )


async def _resolve_mention_context(
    session: AsyncSession,
    *,
    search_space_id: int,
    query: str,
    mentioned_document_ids: list[int] | None,
    mentioned_folder_ids: list[int] | None,
    mentioned_connector_ids: list[int] | None,
    mentioned_connectors: list[MentionedDocumentInfo] | None,
    mentioned_documents: list[MentionedDocumentInfo] | None,
) -> tuple[str, SurfSenseContextSchema | None]:
    """Resolve @-mentions into a rewritten query + per-invocation context.

    Automation always runs in cloud filesystem mode, so we mirror the chat
    ``new_chat`` flow: substitute ``@title`` tokens with canonical
    ``/documents/...`` paths, prepend a ``<mentioned_connectors>`` block, and
    build a ``SurfSenseContextSchema`` that ``KnowledgePriorityMiddleware``
    reads via ``runtime.context``. Returns ``(query, None)`` unchanged when
    there are no mentions.
    """
    has_mentions = bool(
        mentioned_document_ids
        or mentioned_folder_ids
        or mentioned_connector_ids
        or mentioned_connectors
        or mentioned_documents
    )
    if not has_mentions:
        return query, None

    resolved = await resolve_mentions(
        session,
        search_space_id=search_space_id,
        mentioned_documents=mentioned_documents,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_folder_ids=mentioned_folder_ids,
    )
    agent_query = substitute_in_text(query, resolved.token_to_path)

    # ``SurfSenseContextSchema.mentioned_connectors`` is typed ``list[dict]`` and
    # the connector block reads dicts, so dump the pydantic chips once.
    connector_dicts = [c.model_dump() for c in (mentioned_connectors or [])]
    connector_block = _build_connector_block(connector_dicts)
    if connector_block:
        agent_query = f"{connector_block}\n\n<user_query>{agent_query}</user_query>"

    runtime_context = SurfSenseContextSchema(
        search_space_id=search_space_id,
        mentioned_document_ids=list(
            resolved.mentioned_document_ids or (mentioned_document_ids or [])
        ),
        mentioned_folder_ids=list(
            resolved.mentioned_folder_ids or (mentioned_folder_ids or [])
        ),
        mentioned_connector_ids=list(mentioned_connector_ids or []),
        mentioned_connectors=connector_dicts,
    )
    return agent_query, runtime_context


async def run_agent_task(
    *,
    ctx: ActionContext,
    query: str,
    auto_approve_all: bool,
    mentioned_document_ids: list[int] | None = None,
    mentioned_folder_ids: list[int] | None = None,
    mentioned_connector_ids: list[int] | None = None,
    mentioned_connectors: list[MentionedDocumentInfo] | None = None,
    mentioned_documents: list[MentionedDocumentInfo] | None = None,
) -> dict[str, Any]:
    """Invoke multi_agent_chat for one rendered query and return its outcome.

    Opens its own DB session so the executor's bookkeeping session isn't tied
    up for the entire invocation. The LangGraph ``thread_id`` (a fresh UUID)
    is returned as ``agent_session_id`` for later inspection.

    @-mentions (files / folders / connectors) chosen in the task input are
    resolved the same way the chat flow does and forwarded to the agent via the
    per-invocation ``context`` so they actually scope retrieval.
    """
    agent_session_id = str(uuid.uuid4())
    user_id = str(ctx.creator_user_id) if ctx.creator_user_id else None
    decision = "approve" if auto_approve_all else "reject"

    async with async_session_maker() as agent_session:
        deps = await build_dependencies(
            session=agent_session,
            search_space_id=ctx.search_space_id,
            agent_llm_id=ctx.agent_llm_id,
            image_generation_config_id=ctx.image_generation_config_id,
            vision_llm_config_id=ctx.vision_llm_config_id,
        )

        agent = await create_multi_agent_chat_deep_agent(
            llm=deps.llm,
            search_space_id=ctx.search_space_id,
            db_session=agent_session,
            connector_service=deps.connector_service,
            checkpointer=deps.checkpointer,
            user_id=user_id,
            thread_id=None,
            agent_config=deps.agent_config,
            firecrawl_api_key=deps.firecrawl_api_key,
            thread_visibility=ChatVisibility.PRIVATE,
            mentioned_document_ids=mentioned_document_ids,
            image_generation_config_id=ctx.image_generation_config_id,
        )

        agent_query, runtime_context = await _resolve_mention_context(
            agent_session,
            search_space_id=ctx.search_space_id,
            query=query,
            mentioned_document_ids=mentioned_document_ids,
            mentioned_folder_ids=mentioned_folder_ids,
            mentioned_connector_ids=mentioned_connector_ids,
            mentioned_connectors=mentioned_connectors,
            mentioned_documents=mentioned_documents,
        )

        request_id = f"automation:{ctx.run_id}:{ctx.step_id}"
        turn_id = f"{request_id}:{int(time.time() * 1000)}"
        input_state: dict[str, Any] = {
            "messages": [HumanMessage(content=agent_query)],
            "search_space_id": ctx.search_space_id,
            "request_id": request_id,
            "turn_id": turn_id,
        }
        config: dict[str, Any] = {
            "configurable": {
                "thread_id": agent_session_id,
                "request_id": request_id,
                "turn_id": turn_id,
            },
            "recursion_limit": 10_000,
        }
        if runtime_context is not None:
            runtime_context.request_id = request_id
            runtime_context.turn_id = turn_id

        # The compiled graph declares ``context_schema=SurfSenseContextSchema``;
        # mentions only reach ``KnowledgePriorityMiddleware`` via ``context=``.
        invoke_kwargs: dict[str, Any] = {"config": config}
        if runtime_context is not None:
            invoke_kwargs["context"] = runtime_context

        result = await agent.ainvoke(input_state, **invoke_kwargs)

        resumes = 0
        while True:
            state = await agent.aget_state(config)
            if not getattr(state, "interrupts", None):
                break
            if resumes >= _MAX_RESUMES:
                raise RuntimeError(
                    f"agent_task exceeded {_MAX_RESUMES} HITL resume iterations"
                )
            lg_resume_map, routed = build_auto_decisions(state, decision)
            config["configurable"]["surfsense_resume_value"] = routed
            result = await agent.ainvoke(Command(resume=lg_resume_map), **invoke_kwargs)
            resumes += 1

    return {
        "agent_session_id": agent_session_id,
        "final_message": extract_final_assistant_message(result),
        "resumes": resumes,
    }
