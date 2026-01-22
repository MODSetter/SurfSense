"""
Service layer for chat comments and mentions.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import (
    ChatComment,
    ChatCommentMention,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Permission,
    SearchSpaceMembership,
    User,
    has_permission,
)
from app.schemas.chat_comments import (
    AuthorResponse,
    CommentListResponse,
    CommentReplyResponse,
    CommentResponse,
    MentionCommentResponse,
    MentionContextResponse,
    MentionListResponse,
    MentionResponse,
)
from app.services.notification_service import NotificationService
from app.utils.chat_comments import parse_mentions, render_mentions
from app.utils.rbac import check_permission, get_user_permissions


async def get_user_names_for_mentions(
    session: AsyncSession,
    user_ids: set[UUID],
) -> dict[UUID, str]:
    """
    Fetch display names for a set of user IDs.

    Args:
        session: Database session
        user_ids: Set of user UUIDs to look up

    Returns:
        Dictionary mapping user UUID to display name
    """
    if not user_ids:
        return {}

    result = await session.execute(
        select(User.id, User.display_name).filter(User.id.in_(user_ids))
    )
    return {row.id: row.display_name or "Unknown" for row in result.all()}


async def process_mentions(
    session: AsyncSession,
    comment_id: int,
    content: str,
    search_space_id: int,
) -> dict[UUID, int]:
    """
    Parse mentions from content, validate users are members, and insert mention records.

    Args:
        session: Database session
        comment_id: ID of the comment containing mentions
        content: Comment text with @[uuid] mentions
        search_space_id: ID of the search space for membership validation

    Returns:
        Dictionary mapping mentioned user UUID to their mention record ID
    """
    mentioned_uuids = parse_mentions(content)
    if not mentioned_uuids:
        return {}

    # Get valid members from the mentioned UUIDs
    result = await session.execute(
        select(SearchSpaceMembership.user_id).filter(
            SearchSpaceMembership.search_space_id == search_space_id,
            SearchSpaceMembership.user_id.in_(mentioned_uuids),
        )
    )
    valid_member_ids = result.scalars().all()

    # Insert mention records for valid members and collect their IDs
    mentions_map: dict[UUID, int] = {}
    for user_id in valid_member_ids:
        mention = ChatCommentMention(
            comment_id=comment_id,
            mentioned_user_id=user_id,
        )
        session.add(mention)
        await session.flush()
        mentions_map[user_id] = mention.id

    return mentions_map


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

    # Collect all mentioned UUIDs from comments and replies for rendering
    all_mentioned_uuids: set[UUID] = set()
    for comment in top_level_comments:
        all_mentioned_uuids.update(parse_mentions(comment.content))
        for reply in comment.replies:
            all_mentioned_uuids.update(parse_mentions(reply.content))

    # Fetch display names for mentioned users
    user_names = await get_user_names_for_mentions(session, all_mentioned_uuids)

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
                    content_rendered=render_mentions(reply.content, user_names),
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
                content_rendered=render_mentions(comment.content, user_names),
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

    thread = message.thread
    comment = ChatComment(
        message_id=message_id,
        thread_id=thread.id,  # Denormalized for efficient Electric subscriptions
        author_id=user.id,
        content=content,
    )
    session.add(comment)
    await session.flush()

    # Process mentions - returns map of user_id -> mention_id
    mentions_map = await process_mentions(session, comment.id, content, search_space_id)

    await session.commit()
    await session.refresh(comment)

    # Fetch user names for rendering mentions (reuse mentions_map keys)
    user_names = await get_user_names_for_mentions(session, set(mentions_map.keys()))

    # Create notifications for mentioned users (excluding author)
    author_name = user.display_name or user.email
    content_preview = render_mentions(content, user_names)
    for mentioned_user_id, mention_id in mentions_map.items():
        if mentioned_user_id == user.id:
            continue  # Don't notify yourself
        await NotificationService.mention.notify_new_mention(
            session=session,
            mentioned_user_id=mentioned_user_id,
            mention_id=mention_id,
            comment_id=comment.id,
            message_id=message_id,
            thread_id=thread.id,
            thread_title=thread.title or "Untitled thread",
            author_id=str(user.id),
            author_name=author_name,
            author_avatar_url=user.avatar_url,
            author_email=user.email,
            content_preview=content_preview[:200],
            search_space_id=search_space_id,
        )

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
        content_rendered=render_mentions(content, user_names),
        author=author,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_edited=False,
        can_edit=True,
        can_delete=True,
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

    thread = parent_comment.message.thread
    reply = ChatComment(
        message_id=parent_comment.message_id,
        thread_id=thread.id,  # Denormalized for efficient Electric subscriptions
        parent_id=comment_id,
        author_id=user.id,
        content=content,
    )
    session.add(reply)
    await session.flush()

    # Process mentions - returns map of user_id -> mention_id
    mentions_map = await process_mentions(session, reply.id, content, search_space_id)

    await session.commit()
    await session.refresh(reply)

    # Fetch user names for rendering mentions (reuse mentions_map keys)
    user_names = await get_user_names_for_mentions(session, set(mentions_map.keys()))

    # Create notifications for mentioned users (excluding author)
    author_name = user.display_name or user.email
    content_preview = render_mentions(content, user_names)
    for mentioned_user_id, mention_id in mentions_map.items():
        if mentioned_user_id == user.id:
            continue  # Don't notify yourself
        await NotificationService.mention.notify_new_mention(
            session=session,
            mentioned_user_id=mentioned_user_id,
            mention_id=mention_id,
            comment_id=reply.id,
            message_id=parent_comment.message_id,
            thread_id=thread.id,
            thread_title=thread.title or "Untitled thread",
            author_id=str(user.id),
            author_name=author_name,
            author_avatar_url=user.avatar_url,
            author_email=user.email,
            content_preview=content_preview[:200],
            search_space_id=search_space_id,
        )

    author = AuthorResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        email=user.email,
    )

    return CommentReplyResponse(
        id=reply.id,
        content=reply.content,
        content_rendered=render_mentions(content, user_names),
        author=author,
        created_at=reply.created_at,
        updated_at=reply.updated_at,
        is_edited=False,
        can_edit=True,
        can_delete=True,
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
        .options(
            selectinload(ChatComment.author),
            selectinload(ChatComment.message).selectinload(NewChatMessage.thread),
        )
        .filter(ChatComment.id == comment_id)
    )
    comment = result.scalars().first()

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.author_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only edit your own comments",
        )

    search_space_id = comment.message.thread.search_space_id

    # Get existing mentioned user IDs
    existing_result = await session.execute(
        select(ChatCommentMention.mentioned_user_id).filter(
            ChatCommentMention.comment_id == comment_id
        )
    )
    existing_mention_ids = set(existing_result.scalars().all())

    # Parse new mentions from updated content
    new_mention_uuids = set(parse_mentions(content))

    # Validate new mentions are search space members
    if new_mention_uuids:
        valid_result = await session.execute(
            select(SearchSpaceMembership.user_id).filter(
                SearchSpaceMembership.search_space_id == search_space_id,
                SearchSpaceMembership.user_id.in_(new_mention_uuids),
            )
        )
        valid_new_mentions = set(valid_result.scalars().all())
    else:
        valid_new_mentions = set()

    # Compute diff: removed, kept (preserve read status), added
    mentions_to_remove = existing_mention_ids - valid_new_mentions
    mentions_to_add = valid_new_mentions - existing_mention_ids

    # Delete removed mentions
    if mentions_to_remove:
        await session.execute(
            delete(ChatCommentMention).where(
                ChatCommentMention.comment_id == comment_id,
                ChatCommentMention.mentioned_user_id.in_(mentions_to_remove),
            )
        )

    # Add new mentions and collect their IDs for notifications
    new_mentions_map: dict[UUID, int] = {}
    for user_id in mentions_to_add:
        mention = ChatCommentMention(
            comment_id=comment_id,
            mentioned_user_id=user_id,
        )
        session.add(mention)
        await session.flush()
        new_mentions_map[user_id] = mention.id

    comment.content = content

    await session.commit()
    await session.refresh(comment)

    # Fetch user names for rendering mentions
    user_names = await get_user_names_for_mentions(session, valid_new_mentions)

    # Create notifications for newly added mentions (excluding author)
    if new_mentions_map:
        thread = comment.message.thread
        author_name = user.display_name or user.email
        content_preview = render_mentions(content, user_names)
        for mentioned_user_id, mention_id in new_mentions_map.items():
            if mentioned_user_id == user.id:
                continue  # Don't notify yourself
            await NotificationService.mention.notify_new_mention(
                session=session,
                mentioned_user_id=mentioned_user_id,
                mention_id=mention_id,
                comment_id=comment_id,
                message_id=comment.message_id,
                thread_id=thread.id,
                thread_title=thread.title or "Untitled thread",
                author_id=str(user.id),
                author_name=author_name,
                author_avatar_url=user.avatar_url,
                author_email=user.email,
                content_preview=content_preview[:200],
                search_space_id=search_space_id,
            )

    author = AuthorResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        email=user.email,
    )

    return CommentReplyResponse(
        id=comment.id,
        content=comment.content,
        content_rendered=render_mentions(content, user_names),
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


async def get_user_mentions(
    session: AsyncSession,
    user: User,
    search_space_id: int | None = None,
) -> MentionListResponse:
    """
    Get mentions for the current user, optionally filtered by search space.

    Args:
        session: Database session
        user: The current authenticated user
        search_space_id: Optional search space ID to filter mentions

    Returns:
        MentionListResponse with mentions and total count
    """
    # Build query with joins for filtering by search_space_id
    query = (
        select(ChatCommentMention)
        .join(ChatComment, ChatCommentMention.comment_id == ChatComment.id)
        .join(NewChatMessage, ChatComment.message_id == NewChatMessage.id)
        .join(NewChatThread, NewChatMessage.thread_id == NewChatThread.id)
        .options(
            selectinload(ChatCommentMention.comment).selectinload(ChatComment.author),
            selectinload(ChatCommentMention.comment).selectinload(ChatComment.message),
        )
        .filter(ChatCommentMention.mentioned_user_id == user.id)
        .order_by(ChatCommentMention.created_at.desc())
    )

    if search_space_id is not None:
        query = query.filter(NewChatThread.search_space_id == search_space_id)

    result = await session.execute(query)
    mention_records = result.scalars().all()

    # Fetch search space info for context (single query for all unique search spaces)
    thread_ids = {m.comment.message.thread_id for m in mention_records}
    if thread_ids:
        thread_result = await session.execute(
            select(NewChatThread)
            .options(selectinload(NewChatThread.search_space))
            .filter(NewChatThread.id.in_(thread_ids))
        )
        threads_map = {t.id: t for t in thread_result.scalars().all()}
    else:
        threads_map = {}

    mentions = []
    for mention in mention_records:
        comment = mention.comment
        message = comment.message
        thread = threads_map.get(message.thread_id)
        search_space = thread.search_space if thread else None

        author = None
        if comment.author:
            author = AuthorResponse(
                id=comment.author.id,
                display_name=comment.author.display_name,
                avatar_url=comment.author.avatar_url,
                email=comment.author.email,
            )

        content_preview = (
            comment.content[:100] + "..."
            if len(comment.content) > 100
            else comment.content
        )

        mentions.append(
            MentionResponse(
                id=mention.id,
                created_at=mention.created_at,
                comment=MentionCommentResponse(
                    id=comment.id,
                    content_preview=content_preview,
                    author=author,
                    created_at=comment.created_at,
                ),
                context=MentionContextResponse(
                    thread_id=thread.id if thread else 0,
                    thread_title=thread.title or "Untitled" if thread else "Unknown",
                    message_id=message.id,
                    search_space_id=search_space.id if search_space else 0,
                    search_space_name=search_space.name if search_space else "Unknown",
                ),
            )
        )

    return MentionListResponse(
        mentions=mentions,
        total_count=len(mentions),
    )
