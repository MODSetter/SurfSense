"""
Routes for the new chat feature with assistant-ui integration.

These endpoints support the ThreadHistoryAdapter pattern from assistant-ui:
- GET /threads - List threads for sidebar (ThreadListPrimitive)
- POST /threads - Create a new thread
- GET /threads/{thread_id} - Get thread with messages (load)
- PUT /threads/{thread_id} - Update thread (rename, archive)
- DELETE /threads/{thread_id} - Delete thread
- POST /threads/{thread_id}/messages - Append message
"""

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    ChatComment,
    ChatVisibility,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Permission,
    SearchSpace,
    User,
    get_async_session,
    shielded_async_session,
)
from app.schemas.new_chat import (
    NewChatMessageAppend,
    NewChatMessageRead,
    NewChatRequest,
    NewChatThreadCreate,
    NewChatThreadRead,
    NewChatThreadUpdate,
    NewChatThreadVisibilityUpdate,
    NewChatThreadWithMessages,
    PublicChatSnapshotCreateResponse,
    PublicChatSnapshotListResponse,
    RegenerateRequest,
    ResumeRequest,
    ThreadHistoryLoadResponse,
    ThreadListItem,
    ThreadListResponse,
)
from app.tasks.chat.stream_new_chat import stream_new_chat, stream_resume_chat
from app.users import current_active_user
from app.utils.rbac import check_permission

_logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task] = set()

router = APIRouter()


def _try_delete_sandbox(thread_id: int) -> None:
    """Fire-and-forget sandbox + local file deletion so the HTTP response isn't blocked."""
    from app.agents.new_chat.sandbox import (
        delete_local_sandbox_files,
        delete_sandbox,
        is_sandbox_enabled,
    )

    if not is_sandbox_enabled():
        return

    async def _bg() -> None:
        try:
            await delete_sandbox(thread_id)
        except Exception:
            _logger.warning(
                "Background sandbox delete failed for thread %s",
                thread_id,
                exc_info=True,
            )
        try:
            delete_local_sandbox_files(thread_id)
        except Exception:
            _logger.warning(
                "Local sandbox file cleanup failed for thread %s",
                thread_id,
                exc_info=True,
            )

    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(_bg())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        pass


async def check_thread_access(
    session: AsyncSession,
    thread: NewChatThread,
    user: User,
    require_ownership: bool = False,
) -> bool:
    """
    Check if a user has access to a thread based on visibility rules.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE (any member can access) - for read/update operations only
    - Thread is a legacy thread (created_by_id is NULL) - only if user is search space owner

    Args:
        session: Database session
        thread: The thread to check access for
        user: The user requesting access
        require_ownership: If True, ONLY the creator can perform this action (e.g., changing visibility).
                          This is checked FIRST, before visibility rules.

    Returns:
        True if access is granted

    Raises:
        HTTPException: If access is denied
    """
    is_owner = thread.created_by_id == user.id
    is_legacy = thread.created_by_id is None

    # If ownership is required (e.g., changing visibility), ONLY the creator can do it
    # This check comes first to ensure ownership-required operations are always creator-only
    if require_ownership:
        if not is_owner:
            raise HTTPException(
                status_code=403,
                detail="Only the creator of this chat can perform this action",
            )
        return True

    # Shared threads (SEARCH_SPACE) are accessible by any member for read/update operations
    if thread.visibility == ChatVisibility.SEARCH_SPACE:
        return True

    # For legacy threads (created before visibility feature),
    # only the search space owner can access
    if is_legacy:
        search_space_query = select(SearchSpace).filter(
            SearchSpace.id == thread.search_space_id
        )
        search_space_result = await session.execute(search_space_query)
        search_space = search_space_result.scalar_one_or_none()
        is_search_space_owner = search_space and search_space.user_id == user.id

        if is_search_space_owner:
            return True
        # Legacy threads are not accessible to non-owners
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this chat",
        )

    # For read access: owner can access their own private threads
    if is_owner:
        return True

    # Private thread and user is not the owner
    raise HTTPException(
        status_code=403,
        detail="You don't have access to this private chat",
    )


# =============================================================================
# Thread Endpoints
# =============================================================================


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    search_space_id: int,
    limit: int | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all accessible threads for the current user in a search space.
    Returns threads and archived_threads for ThreadListPrimitive.

    A user can see threads that are:
    - Created by them (regardless of visibility)
    - Shared with the search space (visibility = SEARCH_SPACE)
    - Legacy threads with no creator (created_by_id is NULL) - only if user is search space owner

    Args:
        search_space_id: The search space to list threads for
        limit: Optional limit on number of threads to return (applies to active threads only)

    Requires CHATS_READ permission.
    """
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this search space",
        )

        # Check if user is the search space owner (for legacy thread visibility)
        search_space_query = select(SearchSpace).filter(
            SearchSpace.id == search_space_id
        )
        search_space_result = await session.execute(search_space_query)
        search_space = search_space_result.scalar_one_or_none()
        is_search_space_owner = search_space and search_space.user_id == user.id

        # Build filter conditions:
        # 1. Created by the current user (any visibility)
        # 2. Shared with the search space (visibility = SEARCH_SPACE)
        # 3. Legacy threads (created_by_id is NULL) - only visible to search space owner
        filter_conditions = [
            NewChatThread.created_by_id == user.id,
            NewChatThread.visibility == ChatVisibility.SEARCH_SPACE,
        ]

        # Only include legacy threads for the search space owner
        if is_search_space_owner:
            filter_conditions.append(NewChatThread.created_by_id.is_(None))

        query = (
            select(NewChatThread)
            .filter(
                NewChatThread.search_space_id == search_space_id,
                or_(*filter_conditions),
            )
            .order_by(NewChatThread.updated_at.desc())
        )

        result = await session.execute(query)
        all_threads = result.scalars().all()

        # Separate active and archived threads
        threads = []
        archived_threads = []

        for thread in all_threads:
            # Legacy threads (no creator) are treated as own threads for owner
            is_own_thread = thread.created_by_id == user.id or (
                thread.created_by_id is None and is_search_space_owner
            )
            item = ThreadListItem(
                id=thread.id,
                title=thread.title,
                archived=thread.archived,
                visibility=thread.visibility,
                created_by_id=thread.created_by_id,
                is_own_thread=is_own_thread,
                created_at=thread.created_at,
                updated_at=thread.updated_at,
            )
            if thread.archived:
                archived_threads.append(item)
            else:
                threads.append(item)

        # Apply limit to active threads if specified
        if limit is not None and limit > 0:
            threads = threads[:limit]

        return ThreadListResponse(threads=threads, archived_threads=archived_threads)

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching threads: {e!s}",
        ) from None


@router.get("/threads/search", response_model=list[ThreadListItem])
async def search_threads(
    search_space_id: int,
    title: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Search accessible threads by title in a search space.

    A user can search threads that are:
    - Created by them (regardless of visibility)
    - Shared with the search space (visibility = SEARCH_SPACE)
    - Legacy threads with no creator (created_by_id is NULL) - only if user is search space owner

    Args:
        search_space_id: The search space to search in
        title: The search query (case-insensitive partial match)

    Requires CHATS_READ permission.
    """
    try:
        await check_permission(
            session,
            user,
            search_space_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this search space",
        )

        # Check if user is the search space owner (for legacy thread visibility)
        search_space_query = select(SearchSpace).filter(
            SearchSpace.id == search_space_id
        )
        search_space_result = await session.execute(search_space_query)
        search_space = search_space_result.scalar_one_or_none()
        is_search_space_owner = search_space and search_space.user_id == user.id

        # Build filter conditions
        filter_conditions = [
            NewChatThread.created_by_id == user.id,
            NewChatThread.visibility == ChatVisibility.SEARCH_SPACE,
        ]

        # Only include legacy threads for the search space owner
        if is_search_space_owner:
            filter_conditions.append(NewChatThread.created_by_id.is_(None))

        # Search accessible threads by title (case-insensitive)
        query = (
            select(NewChatThread)
            .filter(
                NewChatThread.search_space_id == search_space_id,
                NewChatThread.title.ilike(f"%{title}%"),
                or_(*filter_conditions),
            )
            .order_by(NewChatThread.updated_at.desc())
        )

        result = await session.execute(query)
        threads = result.scalars().all()

        return [
            ThreadListItem(
                id=thread.id,
                title=thread.title,
                archived=thread.archived,
                visibility=thread.visibility,
                created_by_id=thread.created_by_id,
                # Legacy threads (no creator) are treated as own threads for owner
                is_own_thread=(
                    thread.created_by_id == user.id
                    or (thread.created_by_id is None and is_search_space_owner)
                ),
                created_at=thread.created_at,
                updated_at=thread.updated_at,
            )
            for thread in threads
        ]

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while searching threads: {e!s}",
        ) from None


@router.post("/threads", response_model=NewChatThreadRead)
async def create_thread(
    thread: NewChatThreadCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a new chat thread.

    The thread is created with the specified visibility (defaults to PRIVATE).
    The current user is recorded as the creator of the thread.

    Requires CHATS_CREATE permission.
    """
    try:
        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to create chats in this search space",
        )

        now = datetime.now(UTC)
        db_thread = NewChatThread(
            title=thread.title,
            archived=thread.archived,
            visibility=thread.visibility,
            search_space_id=thread.search_space_id,
            created_by_id=user.id,
            updated_at=now,
        )
        session.add(db_thread)
        await session.commit()
        await session.refresh(db_thread)
        return db_thread

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while creating the thread: {e!s}",
        ) from None


@router.get("/threads/{thread_id}", response_model=ThreadHistoryLoadResponse)
async def get_thread_messages(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get a thread with all its messages.
    This is used by ThreadHistoryAdapter.load() to restore conversation.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_READ permission.
    """
    try:
        # Get thread first
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        # Check permission to read chats in this search space
        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this search space",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Get messages with their authors loaded
        messages_result = await session.execute(
            select(NewChatMessage)
            .options(selectinload(NewChatMessage.author))
            .filter(NewChatMessage.thread_id == thread_id)
            .order_by(NewChatMessage.created_at)
        )
        db_messages = messages_result.scalars().all()

        # Return messages in the format expected by assistant-ui
        messages = [
            NewChatMessageRead(
                id=msg.id,
                thread_id=msg.thread_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                author_id=msg.author_id,
                author_display_name=msg.author.display_name if msg.author else None,
                author_avatar_url=msg.author.avatar_url if msg.author else None,
            )
            for msg in db_messages
        ]

        return ThreadHistoryLoadResponse(messages=messages)

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching the thread: {e!s}",
        ) from None


@router.get("/threads/{thread_id}/full", response_model=NewChatThreadWithMessages)
async def get_thread_full(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Get full thread details with all messages.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_READ permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread)
            .options(selectinload(NewChatThread.messages))
            .filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this search space",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Check if thread has any comments
        comment_count = await session.scalar(
            select(func.count())
            .select_from(ChatComment)
            .join(NewChatMessage, ChatComment.message_id == NewChatMessage.id)
            .where(NewChatMessage.thread_id == thread.id)
        )

        return {
            **thread.__dict__,
            "messages": thread.messages,
            "has_comments": (comment_count or 0) > 0,
        }

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching the thread: {e!s}",
        ) from None


@router.put("/threads/{thread_id}", response_model=NewChatThreadRead)
async def update_thread(
    thread_id: int,
    thread_update: NewChatThreadUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update a thread (title, archived status).
    Used for renaming and archiving threads.

    - PRIVATE threads: Only the creator can update
    - SEARCH_SPACE threads: Any member with CHATS_UPDATE permission can update

    Requires CHATS_UPDATE permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        db_thread = result.scalars().first()

        if not db_thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            db_thread.search_space_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this search space",
        )

        # For PRIVATE threads, only the creator can update
        # For SEARCH_SPACE threads, any member with permission can update
        if db_thread.visibility == ChatVisibility.PRIVATE:
            await check_thread_access(session, db_thread, user, require_ownership=True)

        # Update fields
        update_data = thread_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_thread, key, value)

        db_thread.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(db_thread)
        return db_thread

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating the thread: {e!s}",
        ) from None


@router.delete("/threads/{thread_id}", response_model=dict)
async def delete_thread(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a thread and all its messages.

    - PRIVATE threads: Only the creator can delete
    - SEARCH_SPACE threads: Any member with CHATS_DELETE permission can delete

    Requires CHATS_DELETE permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        db_thread = result.scalars().first()

        if not db_thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            db_thread.search_space_id,
            Permission.CHATS_DELETE.value,
            "You don't have permission to delete chats in this search space",
        )

        # For PRIVATE threads, only the creator can delete
        # For SEARCH_SPACE threads, any member with permission can delete
        # Legacy threads (created_by_id is NULL) have no recorded creator,
        # so we skip strict ownership and fall through to legacy handling
        # which allows the search space owner to delete them
        if db_thread.visibility == ChatVisibility.PRIVATE:
            await check_thread_access(
                session,
                db_thread,
                user,
                require_ownership=(db_thread.created_by_id is not None),
            )

        await session.delete(db_thread)
        await session.commit()

        _try_delete_sandbox(thread_id)

        return {"message": "Thread deleted successfully"}

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400, detail="Cannot delete thread due to existing dependencies."
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while deleting the thread: {e!s}",
        ) from None


@router.patch("/threads/{thread_id}/visibility", response_model=NewChatThreadRead)
async def update_thread_visibility(
    thread_id: int,
    visibility_update: NewChatThreadVisibilityUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Update the visibility/sharing settings of a thread.

    Only the creator of the thread can change its visibility.
    - PRIVATE: Only the creator can access the thread (default)
    - SEARCH_SPACE: All members of the search space can access the thread

    Requires CHATS_UPDATE permission.
    """
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        db_thread = result.scalars().first()

        if not db_thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            db_thread.search_space_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this search space",
        )

        # Only the creator can change visibility
        await check_thread_access(session, db_thread, user, require_ownership=True)

        # Update visibility
        db_thread.visibility = visibility_update.visibility
        db_thread.updated_at = datetime.now(UTC)

        await session.commit()
        await session.refresh(db_thread)
        return db_thread

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while updating thread visibility: {e!s}",
        ) from None


# =============================================================================
# Snapshot Endpoints
# =============================================================================


@router.post(
    "/threads/{thread_id}/snapshots", response_model=PublicChatSnapshotCreateResponse
)
async def create_thread_snapshot(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Create a public snapshot of the thread.

    Returns existing snapshot URL if content unchanged (deduplication).
    """
    from app.services.public_chat_service import create_snapshot

    return await create_snapshot(
        session=session,
        thread_id=thread_id,
        user=user,
    )


@router.get(
    "/threads/{thread_id}/snapshots", response_model=PublicChatSnapshotListResponse
)
async def list_thread_snapshots(
    thread_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List all public snapshots for this thread.

    Only the thread owner can view snapshots.
    """
    from app.services.public_chat_service import list_snapshots_for_thread

    return PublicChatSnapshotListResponse(
        snapshots=await list_snapshots_for_thread(
            session=session,
            thread_id=thread_id,
            user=user,
        )
    )


@router.delete("/threads/{thread_id}/snapshots/{snapshot_id}")
async def delete_thread_snapshot(
    thread_id: int,
    snapshot_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Delete a specific snapshot.

    Only the thread owner can delete snapshots.
    """
    from app.services.public_chat_service import delete_snapshot

    await delete_snapshot(
        session=session,
        thread_id=thread_id,
        snapshot_id=snapshot_id,
        user=user,
    )
    return {"message": "Snapshot deleted successfully"}


# =============================================================================
# Message Endpoints
# =============================================================================


@router.post("/threads/{thread_id}/messages", response_model=NewChatMessageRead)
async def append_message(
    thread_id: int,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Append a message to a thread.
    This is used by ThreadHistoryAdapter.append() to persist messages.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_UPDATE permission.
    """
    try:
        # Parse raw body - extract only role and content, ignoring extra fields
        raw_body = await request.json()
        role = raw_body.get("role")
        content = raw_body.get("content")

        if not role:
            raise HTTPException(status_code=400, detail="Missing required field: role")
        if content is None:
            raise HTTPException(
                status_code=400, detail="Missing required field: content"
            )

        # Create message object manually
        message = NewChatMessageAppend(role=role, content=content)
        # Get thread
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this search space",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Convert string role to enum
        role_str = (
            message.role.lower() if isinstance(message.role, str) else message.role
        )
        try:
            message_role = NewChatMessageRole(role_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {message.role}. Must be 'user', 'assistant', or 'system'.",
            ) from None

        # Create message
        db_message = NewChatMessage(
            thread_id=thread_id,
            role=message_role,
            content=message.content,
            author_id=user.id,
        )
        session.add(db_message)

        # Update thread's updated_at timestamp
        thread.updated_at = datetime.now(UTC)

        # Note: Title generation now happens in stream_new_chat.py after the first response
        # using LLM to generate a descriptive title (with truncation as fallback)

        await session.commit()
        await session.refresh(db_message)
        return db_message

    except HTTPException:
        raise
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Database constraint violation. Please check your input data.",
        ) from None
    except OperationalError:
        await session.rollback()
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while appending the message: {e!s}",
        ) from None


@router.get("/threads/{thread_id}/messages", response_model=list[NewChatMessageRead])
async def list_messages(
    thread_id: int,
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    List messages in a thread with pagination.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_READ permission.
    """
    try:
        # Verify thread exists and user has access
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_READ.value,
            "You don't have permission to read chats in this search space",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Get messages
        query = (
            select(NewChatMessage)
            .filter(NewChatMessage.thread_id == thread_id)
            .order_by(NewChatMessage.created_at)
            .offset(skip)
            .limit(limit)
        )

        result = await session.execute(query)
        return result.scalars().all()

    except HTTPException:
        raise
    except OperationalError:
        raise HTTPException(
            status_code=503, detail="Database operation failed. Please try again later."
        ) from None
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching messages: {e!s}",
        ) from None


# =============================================================================
# Chat Streaming Endpoint
# =============================================================================


@router.post("/new_chat")
async def handle_new_chat(
    request: NewChatRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Stream chat responses from the deep agent.

    This endpoint handles the new chat functionality with streaming responses
    using Server-Sent Events (SSE) format compatible with Vercel AI SDK.

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_CREATE permission.
    """
    try:
        # Verify thread exists and user has permission
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == request.chat_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to chat in this search space",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Get search space to check LLM config preferences
        search_space_result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == request.search_space_id)
        )
        search_space = search_space_result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        # Use agent_llm_id from search space for chat operations
        # Positive IDs load from NewLLMConfig database table
        # Negative IDs load from YAML global configs
        # Falls back to -1 (first global config) if not configured
        llm_config_id = (
            search_space.agent_llm_id if search_space.agent_llm_id is not None else -1
        )

        # Release the read-transaction so we don't hold ACCESS SHARE locks
        # on searchspaces/documents for the entire duration of the stream.
        # expire_on_commit=False keeps loaded ORM attrs usable.
        await session.commit()
        # Close the dependency session now so its connection returns to
        # the pool before streaming begins.  Without this, Starlette's
        # BaseHTTPMiddleware cancels the scope on client disconnect and
        # the dependency generator's __aexit__ never runs, orphaning the
        # connection (the "Exception terminating connection" errors).
        await session.close()

        return StreamingResponse(
            stream_new_chat(
                user_query=request.user_query,
                search_space_id=request.search_space_id,
                chat_id=request.chat_id,
                user_id=str(user.id),
                llm_config_id=llm_config_id,
                mentioned_document_ids=request.mentioned_document_ids,
                mentioned_surfsense_doc_ids=request.mentioned_surfsense_doc_ids,
                needs_history_bootstrap=thread.needs_history_bootstrap,
                thread_visibility=thread.visibility,
                current_user_display_name=user.display_name or "A team member",
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {e!s}",
        ) from None


# =============================================================================
# Chat Regeneration Endpoint (Edit/Reload)
# =============================================================================


@router.post("/threads/{thread_id}/regenerate")
async def regenerate_response(
    thread_id: int,
    request: RegenerateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Regenerate the AI response for a chat thread.

    This endpoint supports two operations:
    1. **Edit**: Provide a new `user_query` to replace the last user message and regenerate
    2. **Reload**: Leave `user_query` empty (or None) to regenerate with the same query

    Both operations:
    - Rewind the LangGraph checkpointer to the state before the last AI response
    - Delete the last user message and AI response from the database
    - Stream a new response from that checkpoint

    Access is granted if:
    - User is the creator of the thread
    - Thread visibility is SEARCH_SPACE

    Requires CHATS_UPDATE permission.
    """
    from langchain_core.messages import HumanMessage

    from app.agents.new_chat.checkpointer import get_checkpointer

    try:
        # Verify thread exists and user has permission
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_UPDATE.value,
            "You don't have permission to update chats in this search space",
        )

        # Check thread-level access based on visibility
        await check_thread_access(session, thread, user)

        # Get the checkpointer and state history
        checkpointer = await get_checkpointer()

        config = {"configurable": {"thread_id": str(thread_id)}}

        # Collect checkpoint tuples from the async iterator
        # CheckpointTuple has: config, checkpoint (dict with channel_values), metadata, parent_config
        checkpoint_tuples = []
        async for cp_tuple in checkpointer.alist(config):
            checkpoint_tuples.append(cp_tuple)

        if not checkpoint_tuples:
            raise HTTPException(
                status_code=400, detail="No conversation history found for this thread"
            )

        # Find the checkpoint to rewind to
        # Checkpoints are in reverse chronological order (newest first)
        # We need to find a checkpoint before the last user message was added
        #
        # The checkpointer stores states after each node execution.
        # For a typical conversation flow:
        # - User sends message -> state 1 (with HumanMessage)
        # - Agent responds -> state 2 (with HumanMessage + AIMessage)
        #
        # To regenerate, we need the state BEFORE the last HumanMessage was processed

        target_checkpoint_id = None
        user_query_to_use = request.user_query

        # Look through checkpoints to find the right one
        # We want to find the checkpoint just before the last HumanMessage
        for i, cp_tuple in enumerate(checkpoint_tuples):
            # Access the checkpoint's channel_values which contains "messages"
            checkpoint_data = cp_tuple.checkpoint
            channel_values = checkpoint_data.get("channel_values", {})
            state_messages = channel_values.get("messages", [])

            if state_messages:
                last_msg = state_messages[-1]
                # Find a checkpoint where the last message is NOT a HumanMessage
                # This means we're at a state before the user's last message
                if not isinstance(last_msg, HumanMessage):
                    # If no new user_query provided (reload), extract from a later checkpoint
                    if user_query_to_use is None and i > 0:
                        # Get the user query from a more recent checkpoint
                        for prev_cp_tuple in checkpoint_tuples[:i]:
                            prev_checkpoint_data = prev_cp_tuple.checkpoint
                            prev_channel_values = prev_checkpoint_data.get(
                                "channel_values", {}
                            )
                            prev_messages = prev_channel_values.get("messages", [])
                            for msg in reversed(prev_messages):
                                if isinstance(msg, HumanMessage):
                                    user_query_to_use = msg.content
                                    break
                            if user_query_to_use:
                                break

                    target_checkpoint_id = cp_tuple.config["configurable"][
                        "checkpoint_id"
                    ]
                    break

        # If we couldn't find a good checkpoint, try alternative approaches
        if target_checkpoint_id is None and checkpoint_tuples:
            if len(checkpoint_tuples) == 1:
                # Only one checkpoint - get the user query from it if not provided
                if user_query_to_use is None:
                    checkpoint_data = checkpoint_tuples[0].checkpoint
                    channel_values = checkpoint_data.get("channel_values", {})
                    state_messages = channel_values.get("messages", [])
                    for msg in state_messages:
                        if isinstance(msg, HumanMessage):
                            user_query_to_use = msg.content
                            break
            else:
                # Use the oldest checkpoint
                target_checkpoint_id = checkpoint_tuples[-1].config["configurable"][
                    "checkpoint_id"
                ]

        # If we still don't have a user query, get it from the database
        if user_query_to_use is None:
            # Get the last user message from the database
            last_user_msg_result = await session.execute(
                select(NewChatMessage)
                .filter(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.role == NewChatMessageRole.USER,
                )
                .order_by(NewChatMessage.created_at.desc())
                .limit(1)
            )
            last_user_msg = last_user_msg_result.scalars().first()
            if last_user_msg:
                content = last_user_msg.content
                if isinstance(content, str):
                    user_query_to_use = content
                elif isinstance(content, list):
                    # Extract text from content parts
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            user_query_to_use = part.get("text", "")
                            break
                        elif isinstance(part, str):
                            user_query_to_use = part
                            break

        if user_query_to_use is None:
            raise HTTPException(
                status_code=400,
                detail="Could not determine user query for regeneration. Please provide a user_query.",
            )

        # Get the last two messages to delete AFTER streaming succeeds
        # This prevents data loss if streaming fails
        last_messages_result = await session.execute(
            select(NewChatMessage)
            .filter(NewChatMessage.thread_id == thread_id)
            .order_by(NewChatMessage.created_at.desc())
            .limit(2)
        )
        messages_to_delete = list(last_messages_result.scalars().all())

        message_ids_to_delete = [msg.id for msg in messages_to_delete]

        # Get search space for LLM config
        search_space_result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == request.search_space_id)
        )
        search_space = search_space_result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        llm_config_id = (
            search_space.agent_llm_id if search_space.agent_llm_id is not None else -1
        )

        # Release the read-transaction so we don't hold ACCESS SHARE locks
        # on searchspaces/documents for the entire duration of the stream.
        # expire_on_commit=False keeps loaded ORM attrs (including messages_to_delete PKs) usable.
        await session.commit()
        await session.close()

        # Create a wrapper generator that deletes messages only AFTER streaming succeeds
        # This prevents data loss if streaming fails (network error, LLM error, etc.)
        async def stream_with_cleanup():
            streaming_completed = False
            try:
                async for chunk in stream_new_chat(
                    user_query=user_query_to_use,
                    search_space_id=request.search_space_id,
                    chat_id=thread_id,
                    user_id=str(user.id),
                    llm_config_id=llm_config_id,
                    mentioned_document_ids=request.mentioned_document_ids,
                    mentioned_surfsense_doc_ids=request.mentioned_surfsense_doc_ids,
                    checkpoint_id=target_checkpoint_id,
                    needs_history_bootstrap=thread.needs_history_bootstrap,
                    thread_visibility=thread.visibility,
                    current_user_display_name=user.display_name or "A team member",
                ):
                    yield chunk
                streaming_completed = True
            finally:
                # Only delete old messages if streaming completed successfully.
                # Uses a fresh session since stream_new_chat manages its own.
                if streaming_completed and message_ids_to_delete:
                    try:
                        async with shielded_async_session() as cleanup_session:
                            for msg_id in message_ids_to_delete:
                                _res = await cleanup_session.execute(
                                    select(NewChatMessage).filter(
                                        NewChatMessage.id == msg_id
                                    )
                                )
                                _msg = _res.scalars().first()
                                if _msg:
                                    await cleanup_session.delete(_msg)
                            await cleanup_session.commit()

                            from app.services.public_chat_service import (
                                delete_affected_snapshots,
                            )

                            await delete_affected_snapshots(
                                cleanup_session, thread_id, message_ids_to_delete
                            )
                    except Exception as cleanup_error:
                        _logger.warning(
                            "[regenerate] Failed to delete old messages: %s",
                            cleanup_error,
                        )

        # Return streaming response with checkpoint_id for rewinding
        return StreamingResponse(
            stream_with_cleanup(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during regeneration: {e!s}",
        ) from None


# =============================================================================
# Resume Interrupted Chat Endpoint
# =============================================================================


@router.post("/threads/{thread_id}/resume")
async def resume_chat(
    thread_id: int,
    request: ResumeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    try:
        result = await session.execute(
            select(NewChatThread).filter(NewChatThread.id == thread_id)
        )
        thread = result.scalars().first()

        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")

        await check_permission(
            session,
            user,
            thread.search_space_id,
            Permission.CHATS_CREATE.value,
            "You don't have permission to chat in this search space",
        )

        await check_thread_access(session, thread, user)

        search_space_result = await session.execute(
            select(SearchSpace).filter(SearchSpace.id == request.search_space_id)
        )
        search_space = search_space_result.scalars().first()

        if not search_space:
            raise HTTPException(status_code=404, detail="Search space not found")

        llm_config_id = (
            search_space.agent_llm_id if search_space.agent_llm_id is not None else -1
        )

        decisions = [d.model_dump() for d in request.decisions]

        # Release the read-transaction so we don't hold ACCESS SHARE locks
        # on searchspaces/documents for the entire duration of the stream.
        await session.commit()
        await session.close()

        return StreamingResponse(
            stream_resume_chat(
                chat_id=thread_id,
                search_space_id=request.search_space_id,
                decisions=decisions,
                user_id=str(user.id),
                llm_config_id=llm_config_id,
                thread_visibility=thread.visibility,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during resume: {e!s}",
        ) from None
