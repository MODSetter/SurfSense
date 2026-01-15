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
    NewChatMessageRole,
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
        HTTPException: If message not found or user lacks COMMENTS_READ permission
    """
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
        author = None
        if comment.author:
            author = AuthorResponse(
                id=comment.author.id,
                display_name=comment.author.display_name,
                avatar_url=comment.author.avatar_url,
                email=comment.author.email,
            )

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


async def create_comment(
    session: AsyncSession,
    message_id: int,
    content: str,
    user: User,
) -> CommentResponse:
    """
    Create a top-level comment on an AI response.

    Args:
        session: Database session
        message_id: ID of the message to comment on
        content: Comment text content
        user: The current authenticated user

    Returns:
        CommentResponse for the created comment

    Raises:
        HTTPException: If message not found, not AI response, or user lacks COMMENTS_CREATE permission
    """
    result = await session.execute(
        select(NewChatMessage)
        .options(selectinload(NewChatMessage.thread))
        .filter(NewChatMessage.id == message_id)
    )
    message = result.scalars().first()

    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Validate message is an AI response
    if message.role != NewChatMessageRole.ASSISTANT:
        raise HTTPException(
            status_code=400,
            detail="Comments can only be added to AI responses",
        )

    search_space_id = message.thread.search_space_id

    # Check permission to create comments
    user_permissions = await get_user_permissions(session, user.id, search_space_id)
    if not has_permission(user_permissions, Permission.COMMENTS_CREATE.value):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create comments in this search space",
        )

    comment = ChatComment(
        message_id=message_id,
        author_id=user.id,
        content=content,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    author = AuthorResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        email=user.email,
    )

    return CommentResponse(
        id=comment.id,
        message_id=comment.message_id,
        content=comment.content,
        content_rendered=comment.content,  # TODO: Phase 3
        author=author,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_edited=False,
        can_edit=True,
        can_delete=True,  # Author can always delete their own comment
        reply_count=0,
        replies=[],
    )


async def create_reply(
    session: AsyncSession,
    comment_id: int,
    content: str,
    user: User,
) -> CommentReplyResponse:
    """
    Create a reply to an existing comment.

    Args:
        session: Database session
        comment_id: ID of the parent comment to reply to
        content: Reply text content
        user: The current authenticated user

    Returns:
        CommentReplyResponse for the created reply

    Raises:
        HTTPException: If comment not found, is already a reply, or user lacks COMMENTS_CREATE permission
    """
    # Get parent comment with its message and thread
    result = await session.execute(
        select(ChatComment)
        .options(selectinload(ChatComment.message).selectinload(NewChatMessage.thread))
        .filter(ChatComment.id == comment_id)
    )
    parent_comment = result.scalars().first()

    if not parent_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Validate parent is a top-level comment (cannot reply to a reply)
    if parent_comment.parent_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot reply to a reply",
        )

    search_space_id = parent_comment.message.thread.search_space_id

    # Check permission to create comments
    user_permissions = await get_user_permissions(session, user.id, search_space_id)
    if not has_permission(user_permissions, Permission.COMMENTS_CREATE.value):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create comments in this search space",
        )

    reply = ChatComment(
        message_id=parent_comment.message_id,
        parent_id=comment_id,
        author_id=user.id,
        content=content,
    )
    session.add(reply)
    await session.commit()
    await session.refresh(reply)

    author = AuthorResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        email=user.email,
    )

    return CommentReplyResponse(
        id=reply.id,
        content=reply.content,
        content_rendered=reply.content,  # TODO: Phase 3
        author=author,
        created_at=reply.created_at,
        updated_at=reply.updated_at,
        is_edited=False,
        can_edit=True,
        can_delete=True,  # Author can always delete their own reply
    )


async def update_comment(
    session: AsyncSession,
    comment_id: int,
    content: str,
    user: User,
) -> CommentReplyResponse:
    """
    Update a comment's content (author only).

    Args:
        session: Database session
        comment_id: ID of the comment to update
        content: New comment text content
        user: The current authenticated user

    Returns:
        CommentReplyResponse for the updated comment

    Raises:
        HTTPException: If comment not found or user is not the author
    """
    result = await session.execute(
        select(ChatComment)
        .options(selectinload(ChatComment.author))
        .filter(ChatComment.id == comment_id)
    )
    comment = result.scalars().first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only author can edit their own comment
    if comment.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own comments",
        )

    comment.content = content
    await session.commit()
    await session.refresh(comment)

    author = AuthorResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        email=user.email,
    )

    return CommentReplyResponse(
        id=comment.id,
        content=comment.content,
        content_rendered=comment.content,  # TODO: Phase 3
        author=author,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_edited=comment.updated_at > comment.created_at,
        can_edit=True,
        can_delete=True,
    )


async def delete_comment(
    session: AsyncSession,
    comment_id: int,
    user: User,
) -> dict:
    """
    Delete a comment (author or user with COMMENTS_DELETE permission).

    Args:
        session: Database session
        comment_id: ID of the comment to delete
        user: The current authenticated user

    Returns:
        Dict with deletion confirmation

    Raises:
        HTTPException: If comment not found or user lacks permission to delete
    """
    result = await session.execute(
        select(ChatComment)
        .options(selectinload(ChatComment.message).selectinload(NewChatMessage.thread))
        .filter(ChatComment.id == comment_id)
    )
    comment = result.scalars().first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    is_author = comment.author_id == user.id

    # Check if user has COMMENTS_DELETE permission
    search_space_id = comment.message.thread.search_space_id
    user_permissions = await get_user_permissions(session, user.id, search_space_id)
    can_delete_any = has_permission(user_permissions, Permission.COMMENTS_DELETE.value)

    if not is_author and not can_delete_any:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this comment",
        )

    await session.delete(comment)
    await session.commit()

    return {"message": "Comment deleted successfully", "comment_id": comment_id}
