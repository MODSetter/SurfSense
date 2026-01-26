"""
Service layer for public chat sharing and cloning.
"""

import re
import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import NewChatThread, User

UI_TOOLS = {
    "display_image",
    "link_preview",
    "generate_podcast",
    "scrape_webpage",
    "multi_link_preview",
}


def strip_citations(text: str) -> str:
    """Remove [citation:X] and [citation:doc-X] patterns from text."""
    text = re.sub(r"\[citation:(doc-)?\d+\]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize_content_for_public(content: list | str | None) -> list:
    """Filter message content for public view."""
    if content is None:
        return []

    if isinstance(content, str):
        clean_text = strip_citations(content)
        return [{"type": "text", "text": clean_text}] if clean_text else []

    if not isinstance(content, list):
        return []

    sanitized = []
    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")

        if part_type == "text":
            clean_text = strip_citations(part.get("text", ""))
            if clean_text:
                sanitized.append({"type": "text", "text": clean_text})

        elif part_type == "tool-call":
            if part.get("toolName") in UI_TOOLS:
                sanitized.append(part)

    return sanitized


async def get_author_display(
    session: AsyncSession,
    author_id: UUID | None,
    user_cache: dict[UUID, dict],
) -> dict | None:
    """Transform author UUID to display info."""
    if author_id is None:
        return None

    if author_id not in user_cache:
        result = await session.execute(select(User).filter(User.id == author_id))
        user = result.scalars().first()
        if user:
            user_cache[author_id] = {
                "display_name": user.display_name or "User",
                "avatar_url": user.avatar_url,
            }
        else:
            user_cache[author_id] = {
                "display_name": "Unknown User",
                "avatar_url": None,
            }

    return user_cache[author_id]


async def toggle_public_share(
    session: AsyncSession,
    thread_id: int,
    enabled: bool,
    user: User,
    base_url: str,
) -> dict:
    """
    Enable or disable public sharing for a thread.

    Only the thread owner can toggle public sharing.
    When enabling, generates a new token if one doesn't exist.
    When disabling, keeps the token for potential re-enable.
    """
    result = await session.execute(
        select(NewChatThread).filter(NewChatThread.id == thread_id)
    )
    thread = result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    if thread.created_by_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the creator of this chat can manage public sharing",
        )

    if enabled and not thread.public_share_token:
        thread.public_share_token = secrets.token_urlsafe(48)

    thread.public_share_enabled = enabled

    await session.commit()
    await session.refresh(thread)

    if enabled:
        return {
            "enabled": True,
            "public_url": f"{base_url}/public/{thread.public_share_token}",
            "share_token": thread.public_share_token,
        }

    return {
        "enabled": False,
        "public_url": None,
        "share_token": None,
    }


async def get_public_chat(
    session: AsyncSession,
    share_token: str,
) -> dict:
    """
    Get a public chat by share token.

    Returns sanitized content suitable for public viewing.
    """
    result = await session.execute(
        select(NewChatThread)
        .options(selectinload(NewChatThread.messages))
        .filter(
            NewChatThread.public_share_token == share_token,
            NewChatThread.public_share_enabled.is_(True),
        )
    )
    thread = result.scalars().first()

    if not thread:
        raise HTTPException(status_code=404, detail="Not found")

    user_cache: dict[UUID, dict] = {}

    messages = []
    for msg in sorted(thread.messages, key=lambda m: m.created_at):
        author = await get_author_display(session, msg.author_id, user_cache)
        sanitized_content = sanitize_content_for_public(msg.content)

        messages.append(
            {
                "role": msg.role,
                "content": sanitized_content,
                "author": author,
                "created_at": msg.created_at,
            }
        )

    return {
        "thread": {
            "title": thread.title,
            "created_at": thread.created_at,
        },
        "messages": messages,
    }


async def get_thread_by_share_token(
    session: AsyncSession,
    share_token: str,
) -> NewChatThread | None:
    """Get a thread by its public share token if sharing is enabled."""
    result = await session.execute(
        select(NewChatThread)
        .options(selectinload(NewChatThread.messages))
        .filter(
            NewChatThread.public_share_token == share_token,
            NewChatThread.public_share_enabled.is_(True),
        )
    )
    return result.scalars().first()
