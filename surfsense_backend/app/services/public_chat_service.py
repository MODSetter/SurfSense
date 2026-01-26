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
    """
    Remove [citation:X] and [citation:doc-X] patterns from text.
    Preserves newlines to maintain markdown formatting.
    """
    # Remove citation patterns (including Chinese brackets 【】)
    text = re.sub(r"[\[【]citation:(doc-)?\d+[\]】]", "", text)
    # Collapse multiple spaces/tabs (but NOT newlines) into single space
    text = re.sub(r"[^\S\n]+", " ", text)
    # Normalize excessive blank lines (3+ newlines → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Clean up spaces around newlines
    text = re.sub(r" *\n *", "\n", text)
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


async def get_user_default_search_space(
    session: AsyncSession,
    user_id: UUID,
) -> int | None:
    """
    Get user's default search space for cloning.

    Returns the first search space where user is owner, or None if not found.
    """
    from app.db import SearchSpaceMembership

    result = await session.execute(
        select(SearchSpaceMembership)
        .filter(
            SearchSpaceMembership.user_id == user_id,
            SearchSpaceMembership.is_owner.is_(True),
        )
        .limit(1)
    )
    membership = result.scalars().first()

    if membership:
        return membership.search_space_id

    return None


async def clone_public_chat(
    session: AsyncSession,
    share_token: str,
    user_id: UUID,
) -> dict:
    """
    Clone a public chat to user's account.

    Creates a new private thread with all messages and podcasts.
    """
    import copy

    from app.db import (
        ChatVisibility,
        NewChatMessage,
    )

    source_thread = await get_thread_by_share_token(session, share_token)
    if not source_thread:
        await _create_clone_failure_notification(
            session, user_id, share_token, "Chat not found or no longer public"
        )
        return {"status": "error", "error": "Chat not found or no longer public"}

    try:
        target_search_space_id = await get_user_default_search_space(session, user_id)

        if target_search_space_id is None:
            await _create_clone_failure_notification(
                session, user_id, share_token, "No search space found"
            )
            return {"status": "error", "error": "No search space found"}

        new_thread = NewChatThread(
            title=source_thread.title,
            archived=False,
            visibility=ChatVisibility.PRIVATE,
            search_space_id=target_search_space_id,
            created_by_id=user_id,
            public_share_enabled=False,
        )
        session.add(new_thread)
        await session.flush()

        podcast_id_map: dict[int, int] = {}

        for msg in sorted(source_thread.messages, key=lambda m: m.created_at):
            new_content = copy.deepcopy(msg.content)

            if isinstance(new_content, list):
                for part in new_content:
                    if (
                        isinstance(part, dict)
                        and part.get("type") == "tool-call"
                        and part.get("toolName") == "generate_podcast"
                    ):
                        result = part.get("result", {})
                        old_podcast_id = result.get("podcast_id")
                        if old_podcast_id and old_podcast_id not in podcast_id_map:
                            new_podcast_id = await _clone_podcast(
                                session,
                                old_podcast_id,
                                target_search_space_id,
                                new_thread.id,
                            )
                            if new_podcast_id:
                                podcast_id_map[old_podcast_id] = new_podcast_id

                        if old_podcast_id and old_podcast_id in podcast_id_map:
                            result["podcast_id"] = podcast_id_map[old_podcast_id]

            new_message = NewChatMessage(
                thread_id=new_thread.id,
                role=msg.role,
                content=new_content,
                author_id=msg.author_id,
                created_at=msg.created_at,
            )
            session.add(new_message)

        await session.commit()

        await _create_clone_success_notification(
            session,
            user_id,
            new_thread.id,
            target_search_space_id,
            source_thread.title,
        )

        return {
            "status": "success",
            "thread_id": new_thread.id,
            "search_space_id": target_search_space_id,
        }

    except Exception as e:
        await session.rollback()
        await _create_clone_failure_notification(session, user_id, share_token, str(e))
        return {"status": "error", "error": str(e)}


async def _clone_podcast(
    session: AsyncSession,
    podcast_id: int,
    target_search_space_id: int,
    target_thread_id: int,
) -> int | None:
    """Clone a podcast record and its audio file."""
    import shutil
    import uuid
    from pathlib import Path

    from app.db import Podcast

    result = await session.execute(select(Podcast).filter(Podcast.id == podcast_id))
    original = result.scalars().first()
    if not original:
        return None

    new_file_path = None
    if original.file_location:
        original_path = Path(original.file_location)
        if original_path.exists():
            new_filename = f"{uuid.uuid4()}_podcast.mp3"
            new_dir = Path("podcasts")
            new_dir.mkdir(parents=True, exist_ok=True)
            new_file_path = str(new_dir / new_filename)
            shutil.copy2(original.file_location, new_file_path)

    new_podcast = Podcast(
        title=original.title,
        podcast_transcript=original.podcast_transcript,
        file_location=new_file_path,
        search_space_id=target_search_space_id,
        thread_id=target_thread_id,
    )
    session.add(new_podcast)
    await session.flush()

    return new_podcast.id


async def _create_clone_success_notification(
    session: AsyncSession,
    user_id: UUID,
    thread_id: int,
    search_space_id: int,
    original_title: str,
) -> None:
    """Create success notification for clone operation."""
    from app.db import Notification

    notification = Notification(
        user_id=user_id,
        search_space_id=search_space_id,
        type="chat_cloned",
        title="Chat copied successfully",
        message=f"Your copy of '{original_title}' is ready",
        notification_metadata={
            "thread_id": thread_id,
            "search_space_id": search_space_id,
        },
    )
    session.add(notification)
    await session.commit()


async def _create_clone_failure_notification(
    session: AsyncSession,
    user_id: UUID,
    share_token: str,
    error: str,
) -> None:
    """Create failure notification for clone operation."""
    from app.db import Notification

    notification = Notification(
        user_id=user_id,
        type="chat_clone_failed",
        title="Failed to copy chat",
        message="Could not copy the chat. Please try again.",
        notification_metadata={
            "share_token": share_token,
            "error": error,
        },
    )
    session.add(notification)
    await session.commit()


async def is_podcast_publicly_accessible(
    session: AsyncSession,
    podcast_id: int,
) -> bool:
    """
    Check if a podcast belongs to a publicly shared thread.

    Uses the thread_id foreign key for efficient lookup.
    """
    from app.db import Podcast

    result = await session.execute(
        select(Podcast)
        .options(selectinload(Podcast.thread))
        .filter(Podcast.id == podcast_id)
    )
    podcast = result.scalars().first()

    if not podcast or not podcast.thread:
        return False

    return podcast.thread.public_share_enabled
