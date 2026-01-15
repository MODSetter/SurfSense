"""
Service layer for chat comments and mentions.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import (
    ChatComment,
    NewChatMessage,
    Permission,
    User,
    has_permission,
)
from app.schemas.comments import (
    AuthorResponse,
    CommentListResponse,
    CommentReplyResponse,
    CommentResponse,
)
from app.utils.rbac import check_permission, get_user_permissions


async def get_comments_for_message(
    session: AsyncSession,
    message_id: int,
    user: User,
) -> CommentListResponse:
    """
    Get all comments for a message with their replies.

    Args:
        session: Database session
        message_id: ID of the message to get comments for
        user: The current authenticated user

    Returns:
        CommentListResponse with all top-level comments and their replies

    Raises:
        HTTPException: If message not found or user lacks permission
    """
    # Get the message with its thread to find search_space_id
    result = await session.execute(
        select(NewChatMessage)
        .options(selectinload(NewChatMessage.thread))
        .filter(NewChatMessage.id == message_id)
    )
    message = result.scalars().first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    search_space_id = message.thread.search_space_id

    # Check permission to read comments
    await check_permission(
        session,
        user,
        search_space_id,
        Permission.COMMENTS_READ.value,
        "You don't have permission to read comments in this search space",
    )

    # Get user permissions for can_delete computation
    user_permissions = await get_user_permissions(session, user.id, search_space_id)
    can_delete_any = has_permission(user_permissions, Permission.COMMENTS_DELETE.value)

    # Get top-level comments (parent_id IS NULL) with their authors and replies
    result = await session.execute(
        select(ChatComment)
        .options(
            selectinload(ChatComment.author),
            selectinload(ChatComment.replies).selectinload(ChatComment.author),
        )
        .filter(
            ChatComment.message_id == message_id,
            ChatComment.parent_id.is_(None),
        )
        .order_by(ChatComment.created_at)
    )
    top_level_comments = result.scalars().all()

    comments = []
    for comment in top_level_comments:
        # Build author response
        author = None
        if comment.author:
            author = AuthorResponse(
                id=comment.author.id,
                display_name=comment.author.display_name,
                avatar_url=comment.author.avatar_url,
                email=comment.author.email,
            )

        # Build replies
        replies = []
        for reply in sorted(comment.replies, key=lambda r: r.created_at):
            reply_author = None
            if reply.author:
                reply_author = AuthorResponse(
                    id=reply.author.id,
                    display_name=reply.author.display_name,
                    avatar_url=reply.author.avatar_url,
                    email=reply.author.email,
                )

            is_reply_author = reply.author_id == user.id if reply.author_id else False
            replies.append(
                CommentReplyResponse(
                    id=reply.id,
                    content=reply.content,
                    content_rendered=reply.content,  # TODO: render mentions in Phase 3
                    author=reply_author,
                    created_at=reply.created_at,
                    updated_at=reply.updated_at,
                    is_edited=reply.updated_at > reply.created_at,
                    can_edit=is_reply_author,
                    can_delete=is_reply_author or can_delete_any,
                )
            )

        is_comment_author = comment.author_id == user.id if comment.author_id else False
        comments.append(
            CommentResponse(
                id=comment.id,
                message_id=comment.message_id,
                content=comment.content,
                content_rendered=comment.content,  # TODO: render mentions in Phase 3
                author=author,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_edited=comment.updated_at > comment.created_at,
                can_edit=is_comment_author,
                can_delete=is_comment_author or can_delete_any,
                reply_count=len(replies),
                replies=replies,
            )
        )

    return CommentListResponse(
        comments=comments,
        total_count=len(comments),
    )
