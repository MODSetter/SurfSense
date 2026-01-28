"""
Utilities for working with message content.

Message content in new_chat_messages can be stored in various formats:
- String: Simple text content
- List: Array of content parts [{"type": "text", "text": "..."}, {"type": "tool-call", ...}]
- Dict: Single content object

These utilities help extract and transform content for different use cases.
"""

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def extract_text_content(content: str | dict | list) -> str:
    """Extract plain text content from various message formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        # Handle dict with 'text' key
        if "text" in content:
            return content["text"]
        return str(content)
    if isinstance(content, list):
        # Handle list of parts (e.g., [{"type": "text", "text": "..."}])
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif isinstance(part, str):
                texts.append(part)
        return "\n".join(texts) if texts else ""
    return ""


async def bootstrap_history_from_db(
    session: AsyncSession,
    thread_id: int,
) -> list[HumanMessage | AIMessage]:
    """
    Load message history from database and convert to LangChain format.

    Used for cloned chats where the LangGraph checkpointer has no state,
    but we have messages in the database that should be used as context.

    Args:
        session: Database session
        thread_id: The chat thread ID

    Returns:
        List of LangChain messages (HumanMessage/AIMessage)
    """
    from app.db import NewChatMessage

    result = await session.execute(
        select(NewChatMessage)
        .filter(NewChatMessage.thread_id == thread_id)
        .order_by(NewChatMessage.created_at)
    )
    db_messages = result.scalars().all()

    langchain_messages: list[HumanMessage | AIMessage] = []

    for msg in db_messages:
        text_content = extract_text_content(msg.content)
        if not text_content:
            continue
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=text_content))
        elif msg.role == "assistant":
            langchain_messages.append(AIMessage(content=text_content))

    return langchain_messages
