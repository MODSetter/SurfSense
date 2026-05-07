"""Build ``StreamingContext`` for regenerate streaming."""

from __future__ import annotations

from app.agents.new_chat.filesystem_selection import FilesystemSelection
from app.db import ChatVisibility
from app.tasks.chat.streaming.orchestration.input import StreamingContext
from app.tasks.chat.streaming.orchestration.streaming_context.chat import (
    build_chat_streaming_context,
)


async def build_regenerate_streaming_context(
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
    """Build context for ``stream_regenerate`` execution."""
    return await build_chat_streaming_context(
        user_query=user_query,
        search_space_id=search_space_id,
        chat_id=chat_id,
        user_id=user_id,
        llm_config_id=llm_config_id,
        mentioned_document_ids=mentioned_document_ids,
        mentioned_surfsense_doc_ids=mentioned_surfsense_doc_ids,
        checkpoint_id=checkpoint_id,
        needs_history_bootstrap=needs_history_bootstrap,
        thread_visibility=thread_visibility,
        current_user_display_name=current_user_display_name,
        disabled_tools=disabled_tools,
        filesystem_selection=filesystem_selection,
        request_id=request_id,
        user_image_data_urls=user_image_data_urls,
    )

