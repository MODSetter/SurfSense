"""
Routes for chat comments and mentions.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.db import get_async_session
from app.schemas.chat_comments import (
    CommentBatchRequest,
    CommentBatchResponse,
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
    get_comments_for_messages_batch,
    get_user_mentions,
    update_comment,
)
from app.users import require_session_context

router = APIRouter()


@router.post("/messages/comments/batch", response_model=CommentBatchResponse)
async def batch_list_comments(
    request: CommentBatchRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Batch-fetch comments for multiple messages in one request."""
    return await get_comments_for_messages_batch(session, request.message_ids, auth)


@router.get("/messages/{message_id}/comments", response_model=CommentListResponse)
async def list_comments(
    message_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """List all comments for a message with their replies."""
    return await get_comments_for_message(session, message_id, auth)


@router.post("/messages/{message_id}/comments", response_model=CommentResponse)
async def add_comment(
    message_id: int,
    request: CommentCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Create a top-level comment on an AI response."""
    return await create_comment(session, message_id, request.content, auth)


@router.post("/comments/{comment_id}/replies", response_model=CommentReplyResponse)
async def add_reply(
    comment_id: int,
    request: CommentCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Reply to an existing comment."""
    return await create_reply(session, comment_id, request.content, auth)


@router.put("/comments/{comment_id}", response_model=CommentReplyResponse)
async def edit_comment(
    comment_id: int,
    request: CommentUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Update a comment's content (author only)."""
    return await update_comment(session, comment_id, request.content, auth)


@router.delete("/comments/{comment_id}")
async def remove_comment(
    comment_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """Delete a comment (author or user with COMMENTS_DELETE permission)."""
    return await delete_comment(session, comment_id, auth)


# =============================================================================
# Mention Routes
# =============================================================================


@router.get("/mentions", response_model=MentionListResponse)
async def list_mentions(
    search_space_id: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(require_session_context),
):
    """List mentions for the current user."""
    return await get_user_mentions(session, auth, search_space_id)
