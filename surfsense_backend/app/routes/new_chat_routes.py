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
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.agents.new_chat.filesystem_selection import (
    ClientPlatform,
    FilesystemMode,
    FilesystemSelection,
    LocalFilesystemMount,
)
from app.config import config
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
    AgentToolInfo,
    LocalFilesystemMountPayload,
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
    TokenUsageSummary,
)
from app.services.token_tracking_service import record_token_usage
from app.tasks.chat.stream_new_chat import stream_new_chat, stream_resume_chat
from app.users import current_active_user
from app.utils.rbac import check_permission
from app.utils.user_message_multimodal import (
    split_langchain_human_content,
    split_persisted_user_content_parts,
)

_logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task] = set()

router = APIRouter()


def _resolve_filesystem_selection(
    *,
    mode: str,
    client_platform: str,
    local_mounts: list[LocalFilesystemMountPayload] | None,
) -> FilesystemSelection:
    """Validate and normalize filesystem mode settings from request payload."""
    try:
        resolved_mode = FilesystemMode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filesystem_mode") from exc
    try:
        resolved_platform = ClientPlatform(client_platform)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid client_platform") from exc

    if resolved_mode == FilesystemMode.DESKTOP_LOCAL_FOLDER:
        if not config.ENABLE_DESKTOP_LOCAL_FILESYSTEM:
            raise HTTPException(
                status_code=400,
                detail="Desktop local filesystem mode is disabled on this deployment.",
            )
        if resolved_platform != ClientPlatform.DESKTOP:
            raise HTTPException(
                status_code=400,
                detail="desktop_local_folder mode is only available on desktop runtime.",
            )
        normalized_mounts: list[tuple[str, str]] = []
        seen_mounts: set[str] = set()
        for mount in local_mounts or []:
            mount_id = mount.mount_id.strip()
            root_path = mount.root_path.strip()
            if not mount_id or not root_path:
                continue
            if mount_id in seen_mounts:
                continue
            seen_mounts.add(mount_id)
            normalized_mounts.append((mount_id, root_path))
        if not normalized_mounts:
            raise HTTPException(
                status_code=400,
                detail=(
                    "local_filesystem_mounts must include at least one mount for "
                    "desktop_local_folder mode."
                ),
            )
        return FilesystemSelection(
            mode=resolved_mode,
            client_platform=resolved_platform,
            local_mounts=tuple(
                LocalFilesystemMount(mount_id=mount_id, root_path=root_path)
                for mount_id, root_path in normalized_mounts
            ),
        )

    return FilesystemSelection(
        mode=FilesystemMode.CLOUD,
        client_platform=resolved_platform,
    )


def _find_pre_turn_checkpoint_id(
    checkpoint_tuples: list,
    *,
    turn_id: str,
) -> str | None:
    """Locate the LangGraph checkpoint immediately before ``turn_id`` started.

    ``checkpoint_tuples`` arrives newest-first from
    ``checkpointer.alist(config)``. We walk OLDEST-first (``reversed``)
    and remember the most recent checkpoint that does NOT belong to the
    edited turn. As soon as we cross into the edited turn (a checkpoint
    whose ``turn_id`` matches), we return the previously-tracked
    checkpoint — that's the state immediately before ``turn_id`` began.

    The naive "newest-first, return first non-matching" approach is
    INCORRECT when later turns exist after ``turn_id``: their
    checkpoints also satisfy ``cp_turn_id != turn_id`` and would be
    returned before the real pre-turn boundary is reached.

    Reads from ``cp_tuple.metadata`` (the durable surface promoted from
    ``configurable`` at write time) rather than ``config["configurable"]``
    so the lookup is portable across checkpointer implementations.

    Returns ``None`` when no eligible pre-turn checkpoint exists (e.g.
    the edited turn is the very first turn of the thread). Callers fall
    back to the oldest available checkpoint in that case.
    """

    last_pre_turn_target: str | None = None
    for cp_tuple in reversed(checkpoint_tuples):  # oldest -> newest
        metadata = getattr(cp_tuple, "metadata", None) or {}
        cp_turn_id = metadata.get("turn_id") if isinstance(metadata, dict) else None
        if cp_turn_id == turn_id:
            # Crossed into the edited turn; the previous tracked
            # checkpoint is the rewind target. May be ``None`` if we hit
            # the edited turn on the very first iteration.
            return last_pre_turn_target
        try:
            last_pre_turn_target = cp_tuple.config["configurable"]["checkpoint_id"]
        except (KeyError, TypeError):
            continue
    return last_pre_turn_target


async def _revert_turns_for_regenerate(
    *,
    thread_id: int,
    chat_turn_ids: list[str],
    requester_user_id: str,
) -> dict:
    """Best-effort revert pass for every ``chat_turn_id`` in ``chat_turn_ids``.

    Runs BEFORE the regenerate stream so the frontend can surface
    partial-rollback feedback alongside the new assistant turn. Each
    turn's actions are reverted in their own SAVEPOINTs (handled
    inside :mod:`app.routes.agent_revert_route`'s helpers) so a single
    failure never poisons the batch.

    Sequencing inside the request: revert THEN regenerate. The
    operation is NOT atomic and partial state IS surfaced — see the
    plan's "Sequencing inside the request" note.
    """

    from app.routes.agent_revert_route import (
        RevertTurnActionResult,
        _classify_outcome,
        _OutcomeRollbackError,
        _was_already_reverted,
        _was_already_reverted_batch,
    )
    from app.services.revert_service import (
        can_revert,
        revert_action,
    )

    aggregated_results: list[dict] = []
    # Exhaustive counters keep the response invariant
    # ``total == sum(counters)`` true for ``data-revert-results``.
    counts = {
        "reverted": 0,
        "already_reverted": 0,
        "not_reversible": 0,
        "permission_denied": 0,
        "failed": 0,
        "skipped": 0,
    }

    # Local import keeps the route module's existing imports tidy and
    # avoids a circular dependency at module-load time.
    from app.db import AgentActionLog as _AgentActionLog

    async with shielded_async_session() as session:
        for chat_turn_id in chat_turn_ids:
            rows_stmt = (
                select(_AgentActionLog)
                .where(
                    _AgentActionLog.thread_id == thread_id,
                    _AgentActionLog.chat_turn_id == chat_turn_id,
                )
                .order_by(
                    _AgentActionLog.created_at.desc(),
                    _AgentActionLog.id.desc(),
                )
            )
            rows = (await session.execute(rows_stmt)).scalars().all()

            # Batch idempotency probe across the turn (single SELECT
            # instead of one per row).
            eligible_ids = [r.id for r in rows if r.reverse_of is None]
            already_reverted_map = await _was_already_reverted_batch(
                session, action_ids=eligible_ids
            )

            for action in rows:
                if action.reverse_of is not None:
                    counts["skipped"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="skipped",
                            message="Row is itself a revert action; skipped.",
                        ).model_dump()
                    )
                    continue

                existing_revert_id = already_reverted_map.get(action.id)
                if existing_revert_id is not None:
                    counts["already_reverted"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="already_reverted",
                            new_action_id=existing_revert_id,
                        ).model_dump()
                    )
                    continue

                if not can_revert(
                    requester_user_id=requester_user_id,
                    action=action,
                    is_admin=False,
                ):
                    counts["permission_denied"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="permission_denied",
                            message="You are not allowed to revert this action.",
                        ).model_dump()
                    )
                    continue

                try:
                    async with session.begin_nested():
                        outcome = await revert_action(
                            session,
                            action=action,
                            requester_user_id=requester_user_id,
                        )
                        if outcome.status != "ok":
                            raise _OutcomeRollbackError(outcome)
                except _OutcomeRollbackError as rollback:
                    outcome = rollback.outcome
                    classified = _classify_outcome(outcome)
                    if classified == "permission_denied":
                        counts["permission_denied"] += 1
                    else:
                        counts["not_reversible"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status=classified,
                            message=outcome.message,
                        ).model_dump()
                    )
                    continue
                except IntegrityError:
                    # Concurrent revert won the race against the
                    # pre-flight ``_was_already_reverted`` SELECT.
                    # Surface the winning revert id so the client can
                    # treat this as a successful idempotent op.
                    existing_revert_id = await _was_already_reverted(
                        session, action_id=action.id
                    )
                    counts["already_reverted"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="already_reverted",
                            new_action_id=existing_revert_id,
                        ).model_dump()
                    )
                    continue
                except Exception as err:  # pragma: no cover — defensive
                    _logger.exception(
                        "Unexpected revert failure during regenerate batch "
                        "for action_id=%s",
                        action.id,
                    )
                    counts["failed"] += 1
                    aggregated_results.append(
                        RevertTurnActionResult(
                            action_id=action.id,
                            tool_name=action.tool_name,
                            status="failed",
                            error=str(err) or err.__class__.__name__,
                        ).model_dump()
                    )
                    continue

                counts["reverted"] += 1
                aggregated_results.append(
                    RevertTurnActionResult(
                        action_id=action.id,
                        tool_name=action.tool_name,
                        status="reverted",
                        message=outcome.message,
                        new_action_id=outcome.new_action_id,
                    ).model_dump()
                )

        try:
            await session.commit()
        except Exception:
            _logger.exception(
                "[regenerate-revert] Final commit failed; rolling back batch."
            )
            await session.rollback()

    has_partial = (
        counts["failed"] > 0
        or counts["not_reversible"] > 0
        or counts["permission_denied"] > 0
    )

    return {
        "status": "partial" if has_partial else "ok",
        "chat_turn_ids": chat_turn_ids,
        "total": len(aggregated_results),
        "reverted": counts["reverted"],
        "already_reverted": counts["already_reverted"],
        "not_reversible": counts["not_reversible"],
        "permission_denied": counts["permission_denied"],
        "failed": counts["failed"],
        "skipped": counts["skipped"],
        "results": aggregated_results,
    }


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

        # Get messages with their authors and token usage loaded
        messages_result = await session.execute(
            select(NewChatMessage)
            .options(
                selectinload(NewChatMessage.author),
                selectinload(NewChatMessage.token_usage),
            )
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
                token_usage=TokenUsageSummary.model_validate(msg.token_usage)
                if msg.token_usage
                else None,
                turn_id=msg.turn_id,
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
            .options(
                selectinload(NewChatThread.messages).selectinload(
                    NewChatMessage.token_usage
                ),
            )
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

        # Validate role early (before any DB work)
        role_str = role.lower() if isinstance(role, str) else role
        try:
            message_role = NewChatMessageRole(role_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role: {role}. Must be 'user', 'assistant', or 'system'.",
            ) from None

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

        # Create message. ``turn_id`` is the per-turn correlation id from
        # ``configurable.turn_id`` (added in migration 136) — when the
        # client streams it back to ``appendMessage``, we persist it so
        # C1's edit-from-arbitrary-position can later map this message
        # back to the LangGraph checkpoint that produced its turn.
        raw_turn_id = raw_body.get("turn_id")
        turn_id_value = (
            str(raw_turn_id).strip()
            if isinstance(raw_turn_id, str) and raw_turn_id.strip()
            else None
        )

        db_message = NewChatMessage(
            thread_id=thread_id,
            role=message_role,
            content=content,
            author_id=user.id,
            turn_id=turn_id_value,
        )
        session.add(db_message)

        # Update thread's updated_at timestamp
        thread.updated_at = datetime.now(UTC)

        # flush assigns the PK/defaults without a round-trip SELECT
        await session.flush()

        # Persist token usage if provided (for assistant messages)
        token_usage_data = raw_body.get("token_usage")
        if token_usage_data and message_role == NewChatMessageRole.ASSISTANT:
            await record_token_usage(
                session,
                usage_type="chat",
                search_space_id=thread.search_space_id,
                user_id=user.id,
                prompt_tokens=token_usage_data.get("prompt_tokens", 0),
                completion_tokens=token_usage_data.get("completion_tokens", 0),
                total_tokens=token_usage_data.get("total_tokens", 0),
                model_breakdown=token_usage_data.get("usage"),
                call_details=token_usage_data.get("call_details"),
                thread_id=thread_id,
                message_id=db_message.id,
            )

        await session.commit()

        # Build response manually to avoid lazy-loading the token_usage
        # relationship after commit (which would trigger MissingGreenlet).
        return NewChatMessageRead(
            id=db_message.id,
            thread_id=db_message.thread_id,
            role=db_message.role,
            content=db_message.content,
            created_at=db_message.created_at,
            author_id=db_message.author_id,
            token_usage=None,
            turn_id=db_message.turn_id,
        )

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
            .options(selectinload(NewChatMessage.token_usage))
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
# Agent Tools Endpoint
# =============================================================================


@router.get("/agent/tools", response_model=list[AgentToolInfo])
async def list_agent_tools(
    _user: User = Depends(current_active_user),
):
    """Return the list of built-in agent tools with their metadata.

    Hidden (WIP) tools are excluded from the response.
    """
    from app.agents.new_chat.tools.registry import BUILTIN_TOOLS

    return [
        AgentToolInfo(
            name=t.name,
            description=t.description,
            enabled_by_default=t.enabled_by_default,
        )
        for t in BUILTIN_TOOLS
        if not t.hidden
    ]


# =============================================================================
# Chat Streaming Endpoint
# =============================================================================


@router.post("/new_chat")
async def handle_new_chat(
    request: NewChatRequest,
    http_request: Request,
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
        filesystem_selection = _resolve_filesystem_selection(
            mode=request.filesystem_mode,
            client_platform=request.client_platform,
            local_mounts=request.local_filesystem_mounts,
        )

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

        image_urls = (
            [p.as_data_url() for p in request.user_images]
            if request.user_images
            else None
        )

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
                disabled_tools=request.disabled_tools,
                filesystem_selection=filesystem_selection,
                request_id=getattr(http_request.state, "request_id", "unknown"),
                user_image_data_urls=image_urls,
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
    http_request: Request,
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
        filesystem_selection = _resolve_filesystem_selection(
            mode=request.filesystem_mode,
            client_platform=request.client_platform,
            local_mounts=request.local_filesystem_mounts,
        )

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
        regenerate_image_urls: list[str] = []

        # ---------------------------------------------------------------
        # Edit-from-arbitrary-position. When the client passes
        # ``from_message_id`` we look up its persisted ``turn_id`` (added
        # in migration 136) and pick the checkpoint immediately before
        # that turn started.
        #
        # Legacy graceful-degradation contract:
        #   * Rows persisted BEFORE migration 136 have ``turn_id IS NULL``.
        #     Returning 400 in that case is the wrong UX — the user is
        #     editing an old message in an existing thread and just wants
        #     it to work. We instead skip the checkpoint rewind (the
        #     stream falls back to the latest state) and skip the revert
        #     pass (no chat_turn_id available to walk). Deletion still
        #     uses ``created_at``, so the messages-after-cursor slice is
        #     correct on both legacy and post-136 rows.
        # ---------------------------------------------------------------
        from_message_turn_id: str | None = None
        from_message_created_at: datetime | None = None
        legacy_from_message: bool = False
        if request.from_message_id is not None:
            from_msg_row = await session.execute(
                select(NewChatMessage).filter(
                    NewChatMessage.id == request.from_message_id,
                    NewChatMessage.thread_id == thread_id,
                )
            )
            from_msg = from_msg_row.scalars().first()
            if from_msg is None:
                raise HTTPException(
                    status_code=404,
                    detail="from_message_id not found in this thread.",
                )
            from_message_created_at = from_msg.created_at
            if not from_msg.turn_id:
                # Legacy row — surface the degradation in logs but let
                # the request proceed with the slice-based delete and a
                # cold-start checkpoint.
                legacy_from_message = True
                _logger.warning(
                    "[regenerate] from_message_id=%s on thread=%s has no "
                    "turn_id (legacy row pre-migration-136). Falling back "
                    "to slice-based delete without checkpoint rewind. "
                    "revert_actions=%s will be ignored.",
                    request.from_message_id,
                    thread_id,
                    request.revert_actions,
                )
            else:
                from_message_turn_id = from_msg.turn_id

                # Walk oldest-to-newest and pick the LAST checkpoint whose
                # ``turn_id`` differs from the edited turn — that's the state
                # immediately before this turn started running. We read from
                # ``metadata`` (the durable surface) rather than
                # ``config["configurable"]`` so the lookup works across
                # checkpointer implementations.
                target_checkpoint_id = _find_pre_turn_checkpoint_id(
                    checkpoint_tuples,
                    turn_id=from_message_turn_id,
                )
                if target_checkpoint_id is None and len(checkpoint_tuples) > 0:
                    # Fall back to the oldest checkpoint — better than
                    # 400ing when the agent didn't checkpoint pre-turn
                    # (e.g. very first turn of the thread).
                    target_checkpoint_id = checkpoint_tuples[-1].config["configurable"][
                        "checkpoint_id"
                    ]

        # Look through checkpoints to find the right one
        # We want to find the checkpoint just before the last HumanMessage.
        # We enter this branch when:
        #   * the client did NOT pin ``from_message_id`` (legacy reload/edit), OR
        #   * the client pinned ``from_message_id`` but the row is a
        #     legacy pre-migration-136 row with no ``turn_id`` (we
        #     downgraded to the same heuristic as a regular reload).
        # We DO skip it when a real turn_id pinned ``target_checkpoint_id``
        # — that's the C1 happy path and the heuristic below would just
        # re-derive a worse target.
        if request.from_message_id is None or legacy_from_message:
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
                                        q, imgs = split_langchain_human_content(
                                            msg.content
                                        )
                                        user_query_to_use = q
                                        regenerate_image_urls = imgs
                                        break
                                if user_query_to_use is not None and (
                                    str(user_query_to_use).strip()
                                    or regenerate_image_urls
                                ):
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
                            q, imgs = split_langchain_human_content(msg.content)
                            user_query_to_use = q
                            regenerate_image_urls = imgs
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
                    plain, imgs = split_persisted_user_content_parts(content)
                    user_query_to_use = plain
                    regenerate_image_urls = imgs

        if isinstance(user_query_to_use, list):
            user_query_to_use, regenerate_image_urls = split_langchain_human_content(
                user_query_to_use
            )

        if request.user_images is not None:
            regenerate_image_urls = [p.as_data_url() for p in request.user_images]

        if user_query_to_use is None:
            raise HTTPException(
                status_code=400,
                detail="Could not determine user query for regeneration. Please provide a user_query.",
            )
        if not str(user_query_to_use).strip() and not regenerate_image_urls:
            raise HTTPException(
                status_code=400,
                detail="Could not determine user query for regeneration. Please provide a user_query.",
            )

        # Get the messages to delete AFTER streaming succeeds.
        # This prevents data loss if streaming fails.
        #
        # When ``from_message_id`` is set we slice from that message
        # forward (using ``created_at`` so we also catch any tool/system
        # messages persisted into the same turn). Otherwise
        # we keep the legacy "last 2 messages" rewind.
        if request.from_message_id is not None and from_message_created_at is not None:
            last_messages_result = await session.execute(
                select(NewChatMessage)
                .filter(
                    NewChatMessage.thread_id == thread_id,
                    NewChatMessage.created_at >= from_message_created_at,
                )
                .order_by(NewChatMessage.created_at.desc())
            )
        else:
            last_messages_result = await session.execute(
                select(NewChatMessage)
                .filter(NewChatMessage.thread_id == thread_id)
                .order_by(NewChatMessage.created_at.desc())
                .limit(2)
            )
        messages_to_delete = list(last_messages_result.scalars().all())

        message_ids_to_delete = [msg.id for msg in messages_to_delete]

        # When revert_actions is requested, collect the set of
        # ``chat_turn_id``s present in the slice we're about to delete.
        # Each one will be reverted (best-effort) BEFORE the regenerate
        # stream begins. Legacy rows have ``turn_id=None`` and silently
        # contribute nothing — we already logged the degradation above.
        revert_turn_ids: list[str] = []
        if (
            request.revert_actions
            and request.from_message_id is not None
            and not legacy_from_message
        ):
            seen_turns: set[str] = set()
            for msg in messages_to_delete:
                tid = msg.turn_id
                if tid and tid not in seen_turns:
                    seen_turns.add(tid)
                    revert_turn_ids.append(tid)

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
            # Best-effort revert pass BEFORE the regenerate stream begins.
            # Each turn is reverted independently (per-row SAVEPOINTs
            # inside the route helper) and the per-action results are surfaced
            # on a single ``data-revert-results`` SSE event so the frontend
            # can render any failed rows alongside the new turn. Failures here
            # do NOT abort the regeneration — partial rollback is documented
            # behaviour.
            if revert_turn_ids:
                revert_results = await _revert_turns_for_regenerate(
                    thread_id=thread_id,
                    chat_turn_ids=revert_turn_ids,
                    requester_user_id=str(user.id),
                )
                envelope = {
                    "type": "data-revert-results",
                    "data": revert_results,
                }
                yield f"data: {json.dumps(envelope, default=str)}\n\n".encode()
            try:
                async for chunk in stream_new_chat(
                    user_query=str(user_query_to_use),
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
                    disabled_tools=request.disabled_tools,
                    filesystem_selection=filesystem_selection,
                    request_id=getattr(http_request.state, "request_id", "unknown"),
                    user_image_data_urls=regenerate_image_urls or None,
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
    http_request: Request,
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
        filesystem_selection = _resolve_filesystem_selection(
            mode=request.filesystem_mode,
            client_platform=request.client_platform,
            local_mounts=request.local_filesystem_mounts,
        )

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
                filesystem_selection=filesystem_selection,
                request_id=getattr(http_request.state, "request_id", "unknown"),
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
