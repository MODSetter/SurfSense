"""Top-level chat streaming entrypoints.

For now these orchestrator functions are thin compatibility wrappers around the
current ``stream_new_chat`` / ``stream_resume_chat`` implementations. Routing
calls through this module lets us cut over to the fully modular event relay in
one place later without touching API routes again.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Literal

from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.db import ChatVisibility
from app.tasks.chat.stream_new_chat import stream_new_chat, stream_resume_chat
from app.tasks.chat.streaming.orchestration.event_stream import stream_agent_events
from app.tasks.chat.streaming.orchestration.input import StreamExecutionInput
from app.tasks.chat.streaming.orchestration.output import StreamOutput


async def stream_chat(
    *,
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    mentioned_documents: list[dict[str, Any]] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    user_image_data_urls: list[str] | None = None,
    orchestration_input: StreamExecutionInput | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a new chat turn through the current production pipeline."""
    if orchestration_input is not None:
        result = StreamOutput(
            request_id=request_id,
            turn_id=f"{chat_id}:orchestrator",
            filesystem_mode=(
                filesystem_selection.mode.value if filesystem_selection else "cloud"
            ),
            client_platform=(
                filesystem_selection.client_platform.value
                if filesystem_selection
                else "web"
            ),
        )
        async for frame in stream_agent_events(
            agent=orchestration_input.agent,
            config=orchestration_input.config,
            input_data=orchestration_input.input_data,
            streaming_service=orchestration_input.streaming_service,
            result=result,
            step_prefix=orchestration_input.step_prefix,
            initial_step_id=orchestration_input.initial_step_id,
            initial_step_title=orchestration_input.initial_step_title,
            initial_step_items=orchestration_input.initial_step_items,
            content_builder=orchestration_input.content_builder,
            runtime_context=orchestration_input.runtime_context,
        ):
            yield frame
        return

    async for chunk in stream_new_chat(
        user_query=user_query,
        search_space_id=search_space_id,
        chat_id=chat_id,
        user_id=user_id,
        llm_config_id=llm_config_id,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_surfsense_doc_ids=mentioned_surfsense_doc_ids,
        mentioned_documents=mentioned_documents,
        checkpoint_id=checkpoint_id,
        needs_history_bootstrap=needs_history_bootstrap,
        thread_visibility=thread_visibility,
        current_user_display_name=current_user_display_name,
        disabled_tools=disabled_tools,
        filesystem_selection=filesystem_selection,
        request_id=request_id,
        user_image_data_urls=user_image_data_urls,
    ):
        yield chunk


async def stream_resume(
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
) -> AsyncGenerator[str, None]:
    """Resume an interrupted chat turn through the current production pipeline."""
    async for chunk in stream_resume_chat(
        chat_id=chat_id,
        search_space_id=search_space_id,
        decisions=decisions,
        user_id=user_id,
        llm_config_id=llm_config_id,
        thread_visibility=thread_visibility,
        filesystem_selection=filesystem_selection,
        request_id=request_id,
        disabled_tools=disabled_tools,
    ):
        yield chunk


async def stream_regenerate(
    *,
    user_query: str,
    search_space_id: int,
    chat_id: int,
    user_id: str | None = None,
    llm_config_id: int = -1,
    mentioned_document_ids: list[int] | None = None,
    mentioned_surfsense_doc_ids: list[int] | None = None,
    mentioned_documents: list[dict[str, Any]] | None = None,
    checkpoint_id: str | None = None,
    needs_history_bootstrap: bool = False,
    thread_visibility: ChatVisibility | None = None,
    current_user_display_name: str | None = None,
    disabled_tools: list[str] | None = None,
    filesystem_selection: FilesystemSelection | None = None,
    request_id: str | None = None,
    user_image_data_urls: list[str] | None = None,
    flow: Literal["new", "regenerate"] = "regenerate",
) -> AsyncGenerator[str, None]:
    """Regenerate an assistant turn through the current production pipeline."""
    async for chunk in stream_new_chat(
        user_query=user_query,
        search_space_id=search_space_id,
        chat_id=chat_id,
        user_id=user_id,
        llm_config_id=llm_config_id,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_surfsense_doc_ids=mentioned_surfsense_doc_ids,
        mentioned_documents=mentioned_documents,
        checkpoint_id=checkpoint_id,
        needs_history_bootstrap=needs_history_bootstrap,
        thread_visibility=thread_visibility,
        current_user_display_name=current_user_display_name,
        disabled_tools=disabled_tools,
        filesystem_selection=filesystem_selection,
        request_id=request_id,
        user_image_data_urls=user_image_data_urls,
        flow=flow,
    ):
        yield chunk
