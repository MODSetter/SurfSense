import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.services.llm_service import get_agent_llm
from app.services.new_streaming_service import VercelStreamingService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an inline text autocomplete engine. Your job is to complete the user's text naturally.

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


async def _retrieve_kb_context(
    session: AsyncSession,
    text: str,
    search_space_id: int,
) -> str:
    try:
        retriever = ChucksHybridSearchRetriever(session)
        chunks = await retriever.vector_search(
            query_text=text[-200:],
            top_k=3,
            search_space_id=search_space_id,
        )
        if not chunks:
            return ""
        snippets = []
        for chunk in chunks:
            content = getattr(chunk, "content", None) or getattr(chunk, "chunk_text", "")
            if content:
                snippets.append(content[:300])
        if not snippets:
            return ""
        return KB_CONTEXT_TEMPLATE.format(kb_context="\n\n".join(snippets))
    except Exception as e:
        logger.warning(f"KB search failed for autocomplete, proceeding without context: {e}")
        return ""


async def stream_autocomplete(
    text: str,
    cursor_position: int,
    search_space_id: int,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Build context, call the LLM, and yield SSE-formatted tokens."""
    streaming = VercelStreamingService()
    text_before_cursor = text[:cursor_position] if cursor_position >= 0 else text

    if not text_before_cursor.strip():
        yield streaming.format_message_start()
        yield streaming.format_finish()
        yield streaming.format_done()
        return

    kb_context = await _retrieve_kb_context(session, text_before_cursor, search_space_id)

    llm = await get_agent_llm(session, search_space_id)
    if not llm:
        yield streaming.format_message_start()
        yield streaming.format_error("No LLM configured for this search space")
        yield streaming.format_done()
        return

    system_prompt = SYSTEM_PROMPT
    if kb_context:
        system_prompt += kb_context

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Complete this text:\n{text_before_cursor}"),
    ]

    try:
        yield streaming.format_message_start()
        text_id = streaming.generate_text_id()
        yield streaming.format_text_start(text_id)

        async for chunk in llm.astream(messages):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                yield streaming.format_text_delta(text_id, token)

        yield streaming.format_text_end(text_id)
        yield streaming.format_finish()
        yield streaming.format_done()

    except Exception as e:
        logger.error(f"Autocomplete streaming error: {e}")
        yield streaming.format_error(str(e))
        yield streaming.format_done()
