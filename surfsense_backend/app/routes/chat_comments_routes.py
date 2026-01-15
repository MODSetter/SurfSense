"""
Routes for chat comments and mentions.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import User, get_async_session
from app.schemas.chat_comments import (
    CommentCreateRequest,
    CommentListResponse,
    CommentReplyResponse,
    CommentResponse,
    CommentUpdateRequest,
    MentionListResponse,
)
from app.services.chat_comments_service import (
    create_comment,
    create_reply,
    delete_comment,
    get_comments_for_message,
    get_user_mentions,
    mark_all_mentions_as_read,
    mark_mention_as_read,
    update_comment,
)
from app.users import current_active_user

router = APIRouter()


@router.get("/messages/{message_id}/comments", response_model=CommentListResponse)
async def list_comments(
    message_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """List all comments for a message with their replies."""
    return await get_comments_for_message(session, message_id, user)


@router.post("/messages/{message_id}/comments", response_model=CommentResponse)
async def add_comment(
    message_id: int,
    request: CommentCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Create a top-level comment on an AI response."""
    return await create_comment(session, message_id, request.content, user)


@router.post("/comments/{comment_id}/replies", response_model=CommentReplyResponse)
async def add_reply(
    comment_id: int,
    request: CommentCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Reply to an existing comment."""
    return await create_reply(session, comment_id, request.content, user)


@router.put("/comments/{comment_id}", response_model=CommentReplyResponse)
async def edit_comment(
    comment_id: int,
    request: CommentUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Update a comment's content (author only)."""
    return await update_comment(session, comment_id, request.content, user)


@router.delete("/comments/{comment_id}")
async def remove_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Delete a comment (author or user with COMMENTS_DELETE permission)."""
    return await delete_comment(session, comment_id, user)


# =============================================================================
# Mention Routes
# =============================================================================


@router.get("/mentions", response_model=MentionListResponse)
async def list_mentions(
    search_space_id: int | None = None,
    unread_only: bool = False,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """List mentions for the current user."""
    return await get_user_mentions(session, user, search_space_id, unread_only)


@router.put("/mentions/{mention_id}/read")
async def read_mention(
    mention_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Mark a specific mention as read."""
    return await mark_mention_as_read(session, mention_id, user)


@router.put("/mentions/read-all")
async def read_all_mentions(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """Mark all mentions as read for the current user."""
    return await mark_all_mentions_as_read(session, user)
