"""
Utilities for working with message content.

Message content in new_chat_messages can be stored in various formats:
- String: Simple text content
- List: Array of content parts [{"type": "text", "text": "..."}, {"type": "tool-call", ...}]
- Dict: Single content object

These utilities help extract and transform content for different use cases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.tasks.chat.llm_history_normalizer import (
    assistant_content_to_llm_text,
    user_content_to_llm_content,
)

if TYPE_CHECKING:
    from app.db import ChatVisibility


import re

_FENCE_RE = re.compile(
    r"^```(?:\w+)?\s*\n(.*?)```\s*$",
    re.DOTALL,
)


def strip_markdown_fences(text: str) -> str:
    """Remove a single markdown code fence (```json ... ```) wrapper if present."""
    m = _FENCE_RE.match(text.strip())
    return m.group(1).strip() if m else text


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
    thread_visibility: ChatVisibility | None = None,
) -> list[HumanMessage | AIMessage]:
    """
    Load message history from database and convert to LangChain format.

    Used for cloned chats where the LangGraph checkpointer has no state,
    but we have messages in the database that should be used as context.

    When thread_visibility is SEARCH_SPACE, user messages are prefixed with
    the author's display name so the LLM sees who said what.

    Args:
        session: Database session
        thread_id: The chat thread ID
        thread_visibility: When SEARCH_SPACE, user messages get author prefix

    Returns:
        List of LangChain messages (HumanMessage/AIMessage)
    """
    from app.db import ChatVisibility, NewChatMessage

    is_shared = thread_visibility == ChatVisibility.SEARCH_SPACE
    stmt = (
        select(NewChatMessage)
        .filter(NewChatMessage.thread_id == thread_id)
        .order_by(NewChatMessage.created_at)
    )
    if is_shared:
        stmt = stmt.options(selectinload(NewChatMessage.author))
    result = await session.execute(stmt)
    db_messages = result.scalars().all()

    langchain_messages: list[HumanMessage | AIMessage] = []

    for msg in db_messages:
        if msg.role == "user":
            user_content = user_content_to_llm_content(
                msg.content,
                allow_images=False,
            )
            if not user_content:
                continue
            if is_shared:
                author_name = (
                    msg.author.display_name if msg.author else None
                ) or "A team member"
                if isinstance(user_content, str):
                    user_content = f"**[{author_name}]:** {user_content}"
                elif user_content and user_content[0].get("type") == "text":
                    user_content[0] = {
                        **user_content[0],
                        "text": f"**[{author_name}]:** {user_content[0].get('text', '')}",
                    }
            langchain_messages.append(HumanMessage(content=user_content))
        elif msg.role == "assistant":
            assistant_text = assistant_content_to_llm_text(msg.content)
            if assistant_text:
                langchain_messages.append(AIMessage(content=assistant_text))

    return langchain_messages
