import logging
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.llm_service import get_vision_llm
from app.services.new_streaming_service import VercelStreamingService

logger = logging.getLogger(__name__)

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


async def stream_vision_autocomplete(
    screenshot_data_url: str,
    search_space_id: int,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Analyze a screenshot with the vision LLM and stream a text completion."""
    streaming = VercelStreamingService()

    llm = await get_vision_llm(session, search_space_id)
    if not llm:
        yield streaming.format_message_start()
        yield streaming.format_error("No Vision LLM configured for this search space")
        yield streaming.format_done()
        return

    messages = [
        SystemMessage(content=VISION_SYSTEM_PROMPT),
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
        logger.error(f"Vision autocomplete streaming error: {e}")
        yield streaming.format_error(str(e))
        yield streaming.format_done()
