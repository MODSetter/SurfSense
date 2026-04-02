import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.services.llm_service import get_agent_llm
from app.services.new_streaming_service import VercelStreamingService
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autocomplete", tags=["autocomplete"])

AUTOCOMPLETE_SYSTEM_PROMPT = """You are an inline text autocomplete engine. Your job is to complete the user's text naturally.

Rules:
- Output ONLY the continuation text. Do NOT repeat what the user already typed.
- Keep completions concise: 1-3 sentences maximum.
- Match the user's tone, style, and language.
- If knowledge base context is provided, use it to make the completion factually accurate and personalized.
- Do NOT add quotes, explanations, or meta-commentary.
- Do NOT start with a space unless grammatically required.
- If you cannot produce a useful completion, output nothing."""

KB_CONTEXT_TEMPLATE = """
Relevant knowledge base context (use this to personalize the completion):
---
{kb_context}
---
"""


async def _stream_autocomplete(
    text: str,
    cursor_position: int,
    search_space_id: int,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Stream an autocomplete response with KB context."""
    streaming_service = VercelStreamingService()

    try:
        # Text before cursor is what we're completing
        text_before_cursor = text[:cursor_position] if cursor_position >= 0 else text

        if not text_before_cursor.strip():
            yield streaming_service.format_message_start()
            yield streaming_service.format_finish()
            yield streaming_service.format_done()
            return

        # Fast KB lookup: vector-only search, top 3 chunks, no planner LLM
        kb_context = ""
        try:
            retriever = ChucksHybridSearchRetriever(session)
            chunks = await retriever.vector_search(
                query_text=text_before_cursor[-200:],  # last 200 chars for relevance
                top_k=3,
                search_space_id=search_space_id,
            )
            if chunks:
                kb_snippets = []
                for chunk in chunks:
                    content = getattr(chunk, "content", None) or getattr(chunk, "chunk_text", "")
                    if content:
                        kb_snippets.append(content[:300])
                if kb_snippets:
                    kb_context = KB_CONTEXT_TEMPLATE.format(
                        kb_context="\n\n".join(kb_snippets)
                    )
        except Exception as e:
            logger.warning(f"KB search failed for autocomplete, proceeding without context: {e}")

        # Get the search space's configured LLM
        llm = await get_agent_llm(session, search_space_id)
        if not llm:
            yield streaming_service.format_message_start()
            error_msg = "No LLM configured for this search space"
            yield streaming_service.format_error(error_msg)
            yield streaming_service.format_done()
            return

        system_prompt = AUTOCOMPLETE_SYSTEM_PROMPT
        if kb_context:
            system_prompt += kb_context

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Complete this text:\n{text_before_cursor}"),
        ]

        # Stream the response
        yield streaming_service.format_message_start()
        text_id = streaming_service.generate_text_id()
        yield streaming_service.format_text_start(text_id)

        async for chunk in llm.astream(messages):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                yield streaming_service.format_text_delta(text_id, token)

        yield streaming_service.format_text_end(text_id)
        yield streaming_service.format_finish()
        yield streaming_service.format_done()

    except Exception as e:
        logger.error(f"Autocomplete streaming error: {e}")
        yield streaming_service.format_error(str(e))
        yield streaming_service.format_done()


@router.post("/stream")
async def autocomplete_stream(
    text: str = Query(..., description="Current text in the input field"),
    cursor_position: int = Query(-1, description="Cursor position in the text (-1 for end)"),
    search_space_id: int = Query(..., description="Search space ID for KB context and LLM config"),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Stream an autocomplete suggestion based on the current text and KB context."""
    if cursor_position < 0:
        cursor_position = len(text)

    return StreamingResponse(
        _stream_autocomplete(text, cursor_position, search_space_id, session),
        media_type="text/event-stream",
        headers={
            **VercelStreamingService.get_response_headers(),
            "X-Accel-Buffering": "no",
        },
    )
