import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.retriever.chunks_hybrid_search import ChucksHybridSearchRetriever
from app.services.llm_service import get_vision_llm
from app.services.new_streaming_service import VercelStreamingService

logger = logging.getLogger(__name__)

KB_TOP_K = 5
KB_MAX_CHARS = 4000

EXTRACT_QUERY_PROMPT = """Look at this screenshot and describe in 1-2 short sentences what the user is working on and what topic they need to write about. Be specific about the subject matter. Output ONLY the description, nothing else."""

EXTRACT_QUERY_PROMPT_WITH_APP = """The user is currently in the application "{app_name}" with the window titled "{window_title}".

Look at this screenshot and describe in 1-2 short sentences what the user is working on and what topic they need to write about. Be specific about the subject matter. Output ONLY the description, nothing else."""

VISION_SYSTEM_PROMPT = """You are a smart writing assistant that analyzes the user's screen to draft or complete text.

You will receive a screenshot of the user's screen. Your job:
1. Analyze the ENTIRE screenshot to understand what the user is working on (email thread, chat conversation, document, code editor, form, etc.).
2. Identify the text area where the user will type.
3. Based on the full visual context, generate the text the user most likely wants to write.

Key behavior:
- If the text area is EMPTY, draft a full response or message based on what you see on screen (e.g., reply to an email, respond to a chat message, continue a document).
- If the text area already has text, continue it naturally.

Rules:
- Output ONLY the text to be inserted. No quotes, no explanations, no meta-commentary.
- Be concise but complete — a full thought, not a fragment.
- Match the tone and formality of the surrounding context.
- If the screen shows code, write code. If it shows a casual chat, be casual. If it shows a formal email, be formal.
- Do NOT describe the screenshot or explain your reasoning.
- If you cannot determine what to write, output nothing."""

APP_CONTEXT_BLOCK = """

The user is currently working in "{app_name}" (window: "{window_title}"). Use this to understand the type of application and adapt your tone and format accordingly."""

KB_CONTEXT_BLOCK = """

You also have access to the user's knowledge base documents below. Use them to write more accurate, informed, and contextually relevant text. Do NOT cite or reference the documents explicitly — just let the knowledge inform your writing naturally.

<knowledge_base>
{kb_context}
</knowledge_base>"""


def _build_system_prompt(app_name: str, window_title: str, kb_context: str) -> str:
    """Assemble the system prompt from optional context blocks."""
    prompt = VISION_SYSTEM_PROMPT
    if app_name:
        prompt += APP_CONTEXT_BLOCK.format(app_name=app_name, window_title=window_title)
    if kb_context:
        prompt += KB_CONTEXT_BLOCK.format(kb_context=kb_context)
    return prompt


def _is_vision_unsupported_error(e: Exception) -> bool:
    """Check if an exception indicates the model doesn't support vision/images."""
    msg = str(e).lower()
    return "content must be a string" in msg or "does not support image" in msg


async def _extract_query_from_screenshot(
    llm, screenshot_data_url: str,
    app_name: str = "", window_title: str = "",
) -> str | None:
    """Ask the Vision LLM to describe what the user is working on.

    Raises vision-unsupported errors so the caller can return a
    friendly message immediately instead of retrying with astream.
    """
    if app_name:
        prompt_text = EXTRACT_QUERY_PROMPT_WITH_APP.format(
            app_name=app_name, window_title=window_title,
        )
    else:
        prompt_text = EXTRACT_QUERY_PROMPT

    try:
        response = await llm.ainvoke([
            HumanMessage(content=[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": screenshot_data_url}},
            ]),
        ])
        query = response.content.strip() if hasattr(response, "content") else ""
        return query if query else None
    except Exception as e:
        if _is_vision_unsupported_error(e):
            raise
        logger.warning(f"Failed to extract query from screenshot: {e}")
        return None


async def _search_knowledge_base(
    session: AsyncSession, search_space_id: int, query: str
) -> str:
    """Search the KB and return formatted context string."""
    try:
        retriever = ChucksHybridSearchRetriever(session)
        results = await retriever.hybrid_search(
            query_text=query,
            top_k=KB_TOP_K,
            search_space_id=search_space_id,
        )

        if not results:
            return ""

        parts: list[str] = []
        char_count = 0
        for doc in results:
            title = doc.get("document", {}).get("title", "Untitled")
            for chunk in doc.get("chunks", []):
                content = chunk.get("content", "").strip()
                if not content:
                    continue
                entry = f"[{title}]\n{content}"
                if char_count + len(entry) > KB_MAX_CHARS:
                    break
                parts.append(entry)
                char_count += len(entry)
            if char_count >= KB_MAX_CHARS:
                break

        return "\n\n---\n\n".join(parts)
    except Exception as e:
        logger.warning(f"KB search failed, proceeding without context: {e}")
        return ""


async def stream_vision_autocomplete(
    screenshot_data_url: str,
    search_space_id: int,
    session: AsyncSession,
    *,
    app_name: str = "",
    window_title: str = "",
) -> AsyncGenerator[str, None]:
    """Analyze a screenshot with the vision LLM and stream a text completion.

    Pipeline:
    1. Extract a search query from the screenshot (non-streaming)
    2. Search the knowledge base for relevant context
    3. Stream the final completion with screenshot + KB + app context
    """
    streaming = VercelStreamingService()
    vision_error_msg = (
        "The selected model does not support vision. "
        "Please set a vision-capable model (e.g. GPT-4o, Gemini) in your search space settings."
    )

    llm = await get_vision_llm(session, search_space_id)
    if not llm:
        yield streaming.format_message_start()
        yield streaming.format_error("No Vision LLM configured for this search space")
        yield streaming.format_done()
        return

    kb_context = ""
    try:
        query = await _extract_query_from_screenshot(
            llm, screenshot_data_url, app_name=app_name, window_title=window_title,
        )
    except Exception as e:
        logger.warning(f"Vision autocomplete: selected model does not support vision: {e}")
        yield streaming.format_message_start()
        yield streaming.format_error(vision_error_msg)
        yield streaming.format_done()
        return

    if query:
        kb_context = await _search_knowledge_base(session, search_space_id, query)

    system_prompt = _build_system_prompt(app_name, window_title, kb_context)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=[
            {
                "type": "text",
                "text": "Analyze this screenshot. Understand the full context of what the user is working on, then generate the text they most likely want to write in the active text area.",
            },
            {
                "type": "image_url",
                "image_url": {"url": screenshot_data_url},
            },
        ]),
    ]

    text_started = False
    text_id = ""
    try:
        yield streaming.format_message_start()
        text_id = streaming.generate_text_id()
        yield streaming.format_text_start(text_id)
        text_started = True

        async for chunk in llm.astream(messages):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            if token:
                yield streaming.format_text_delta(text_id, token)

        yield streaming.format_text_end(text_id)
        yield streaming.format_finish()
        yield streaming.format_done()

    except Exception as e:
        if text_started:
            yield streaming.format_text_end(text_id)

        if _is_vision_unsupported_error(e):
            logger.warning(f"Vision autocomplete: selected model does not support vision: {e}")
            yield streaming.format_error(vision_error_msg)
        else:
            logger.error(f"Vision autocomplete streaming error: {e}")
            yield streaming.format_error(str(e))
        yield streaming.format_done()
