"""
Routes for the new chat feature with assistant-ui integration.

These endpoints support the ThreadHistoryAdapter pattern from assistant-ui:
- GET /threads - List threads for sidebar (ThreadListPrimitive)
- POST /threads - Create a new thread
- GET /threads/{thread_id} - Get thread with messages (load)
- PUT /threads/{thread_id} - Update thread (rename, archive)
- DELETE /threads/{thread_id} - Delete thread
- POST /threads/{thread_id}/messages - Append message
- POST /attachments/process - Process attachments for chat context
"""

import contextlib
import os
import tempfile
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db import (
    ChatVisibility,
    NewChatMessage,
    NewChatMessageRole,
    NewChatThread,
    Permission,
    SearchSpace,
    User,
    get_async_session,
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
    ThreadHistoryLoadResponse,
    ThreadListItem,
    ThreadListResponse,
)
from app.tasks.chat.stream_new_chat import stream_new_chat
from app.users import current_active_user
from app.utils.rbac import check_permission

router = APIRouter()


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
    - Thread visibility is SEARCH_SPACE (any member can access)
    - Thread is a legacy thread (created_by_id is NULL) - only if user is search space owner

    Args:
        session: Database session
        thread: The thread to check access for
        user: The user requesting access
        require_ownership: If True, only the creator can access (for edit/delete operations)
                          For SEARCH_SPACE threads, any member with permission can access
                          Legacy threads (NULL creator) are accessible by search space owner

    Returns:
        True if access is granted

    Raises:
        HTTPException: If access is denied
    """
    is_owner = thread.created_by_id == user.id
    is_legacy = thread.created_by_id is None

    # Shared threads (SEARCH_SPACE) are accessible by any member
    # This check comes first so shared threads are always accessible
    if thread.visibility == ChatVisibility.SEARCH_SPACE:
        # For ownership-required operations on shared threads, any member can proceed
        # (permission check is done at route level)
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

    # If ownership is required, only the creator can access
    if require_ownership:
        if not is_owner:
            raise HTTPException(
                status_code=403,
                detail="Only the creator of this chat can perform this action",
            )
        return True

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
        # Get thread with messages
        result = await session.execute(
            select(NewChatThread)
            .options(selectinload(NewChatThread.messages))
            .filter(NewChatThread.id == thread_id)
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

        # Return messages in the format expected by assistant-ui
        messages = [
            NewChatMessageRead(
                id=msg.id,
                thread_id=msg.thread_id,
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
            )
            for msg in thread.messages
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

        return thread

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
        if db_thread.visibility == ChatVisibility.PRIVATE:
            await check_thread_access(session, db_thread, user, require_ownership=True)

        await session.delete(db_thread)
        await session.commit()
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
        )
        session.add(db_message)

        # Update thread's updated_at timestamp
        thread.updated_at = datetime.now(UTC)

        # Auto-generate title from first user message if title is still default
        if thread.title == "New Chat" and role_str == "user":
            # Extract text content for title
            content = message.content
            if isinstance(content, str):
                title_text = content
            elif isinstance(content, list):
                # Find first text content
                title_text = ""
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        title_text = part.get("text", "")
                        break
                    elif isinstance(part, str):
                        title_text = part
                        break
            else:
                title_text = str(content)

            # Truncate title
            if title_text:
                thread.title = title_text[:100] + (
                    "..." if len(title_text) > 100 else ""
                )

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

        # Return streaming response
        return StreamingResponse(
            stream_new_chat(
                user_query=request.user_query,
                search_space_id=request.search_space_id,
                chat_id=request.chat_id,
                session=session,
                llm_config_id=llm_config_id,
                attachments=request.attachments,
                mentioned_document_ids=request.mentioned_document_ids,
                mentioned_surfsense_doc_ids=request.mentioned_surfsense_doc_ids,
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
# Attachment Processing Endpoint
# =============================================================================


@router.post("/attachments/process")
async def process_attachment(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    """
    Process an attachment file and extract its content as markdown.

    This endpoint uses the configured ETL service to parse files and return
    the extracted content that can be used as context in chat messages.

    Supported file types depend on the configured ETL_SERVICE:
    - Markdown/Text files: .md, .markdown, .txt (always supported)
    - Audio files: .mp3, .mp4, .mpeg, .mpga, .m4a, .wav, .webm (if STT configured)
    - Documents: .pdf, .docx, .doc, .pptx, .xlsx (depends on ETL service)

    Returns:
        JSON with attachment id, name, type, and extracted content
    """
    from app.config import config as app_config

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    filename = file.filename
    attachment_id = str(uuid.uuid4())

    try:
        # Save file to a temporary location
        file_ext = os.path.splitext(filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_path = temp_file.name
            content = await file.read()
            temp_file.write(content)

        extracted_content = ""

        # Process based on file type
        if file_ext in (".md", ".markdown", ".txt"):
            # For text/markdown files, read content directly
            with open(temp_path, encoding="utf-8") as f:
                extracted_content = f.read()

        elif file_ext in (".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"):
            # Audio files - transcribe if STT service is configured
            if not app_config.STT_SERVICE:
                raise HTTPException(
                    status_code=422,
                    detail="Audio transcription is not configured. Please set STT_SERVICE.",
                )

            stt_service_type = (
                "local" if app_config.STT_SERVICE.startswith("local/") else "external"
            )

            if stt_service_type == "local":
                from app.services.stt_service import stt_service

                result = stt_service.transcribe_file(temp_path)
                extracted_content = result.get("text", "")
            else:
                from litellm import atranscription

                with open(temp_path, "rb") as audio_file:
                    transcription_kwargs = {
                        "model": app_config.STT_SERVICE,
                        "file": audio_file,
                        "api_key": app_config.STT_SERVICE_API_KEY,
                    }
                    if app_config.STT_SERVICE_API_BASE:
                        transcription_kwargs["api_base"] = (
                            app_config.STT_SERVICE_API_BASE
                        )

                    transcription_response = await atranscription(
                        **transcription_kwargs
                    )
                    extracted_content = transcription_response.get("text", "")

            if extracted_content:
                extracted_content = (
                    f"# Transcription of {filename}\n\n{extracted_content}"
                )

        else:
            # Document files - use configured ETL service
            if app_config.ETL_SERVICE == "UNSTRUCTURED":
                from langchain_unstructured import UnstructuredLoader

                from app.utils.document_converters import convert_document_to_markdown

                loader = UnstructuredLoader(
                    temp_path,
                    mode="elements",
                    post_processors=[],
                    languages=["eng"],
                    include_orig_elements=False,
                    include_metadata=False,
                    strategy="auto",
                )
                docs = await loader.aload()
                extracted_content = await convert_document_to_markdown(docs)

            elif app_config.ETL_SERVICE == "LLAMACLOUD":
                from llama_cloud_services import LlamaParse
                from llama_cloud_services.parse.utils import ResultType

                parser = LlamaParse(
                    api_key=app_config.LLAMA_CLOUD_API_KEY,
                    num_workers=1,
                    verbose=False,
                    language="en",
                    result_type=ResultType.MD,
                )
                result = await parser.aparse(temp_path)
                markdown_documents = await result.aget_markdown_documents(
                    split_by_page=False
                )

                if markdown_documents:
                    extracted_content = "\n\n".join(
                        doc.text for doc in markdown_documents
                    )

            elif app_config.ETL_SERVICE == "DOCLING":
                from app.services.docling_service import create_docling_service

                docling_service = create_docling_service()
                result = await docling_service.process_document(temp_path, filename)
                extracted_content = result.get("content", "")

            else:
                raise HTTPException(
                    status_code=422,
                    detail=f"ETL service not configured or unsupported file type: {file_ext}",
                )

        # Clean up temp file
        with contextlib.suppress(Exception):
            os.unlink(temp_path)

        if not extracted_content:
            raise HTTPException(
                status_code=422,
                detail=f"Could not extract content from file: {filename}",
            )

        # Determine attachment type (must be one of: "image", "document", "file")
        # assistant-ui only supports these three types
        if file_ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            attachment_type = "image"
        else:
            # All other files (including audio, documents, text) are treated as "document"
            attachment_type = "document"

        return {
            "id": attachment_id,
            "name": filename,
            "type": attachment_type,
            "content": extracted_content,
            "contentLength": len(extracted_content),
        }

    except HTTPException:
        raise
    except Exception as e:
        # Clean up temp file on error
        with contextlib.suppress(Exception):
            os.unlink(temp_path)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process attachment: {e!s}",
        ) from e
