"""``GET /api/threads/{thread_id}/actions``: list agent action-log entries.

Pairs with ``POST /api/threads/{thread_id}/revert/{action_id}`` (see
``agent_revert_route.py``). The action log is the read-side surface for
the audit/undo UI: it returns a paginated list of every tool call
recorded by :class:`ActionLogMiddleware` against the thread, plus
metadata about whether the action is reversible and whether it has
already been reverted.

The route is gated by the same ``SURFSENSE_ENABLE_ACTION_LOG`` flag that
controls the middleware. When the flag is off the endpoint returns 503
so the UI can detect "this deployment doesn't have the action log
enabled" without 404-ing on a missing route.

The list is ordered DESC by ``created_at`` (newest first) so the
revert UI can render a familiar reverse-chronological feed without an
additional client-side sort.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.feature_flags import get_flags
from app.db import (
    AgentActionLog,
    NewChatThread,
    Permission,
    User,
    get_async_session,
)
from app.users import current_active_user
from app.utils.rbac import check_permission

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class AgentActionRead(BaseModel):
    """One row of the action log surfaced to the client."""

    id: int
    thread_id: int
    user_id: str | None
    search_space_id: int
    tool_name: str
    args: dict[str, Any] | None
    result_id: str | None
    reversible: bool
    reverse_descriptor: dict[str, Any] | None
    error: dict[str, Any] | None
    reverse_of: int | None
    reverted_by_action_id: int | None
    is_revert_action: bool
    # Correlation ids added in migration 135. ``tool_call_id`` is the
    # LangChain tool-call id (joinable to ``data-action-log`` SSE events
    # via ``langchainToolCallId``). ``chat_turn_id`` is the per-turn id
    # from ``configurable.turn_id`` (used by the
    # ``revert-turn/{chat_turn_id}`` endpoint).
    tool_call_id: str | None = None
    chat_turn_id: str | None = None
    created_at: datetime


class AgentActionListResponse(BaseModel):
    """Paginated list response for the action log."""

    items: list[AgentActionRead]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _flag_guard() -> None:
    flags = get_flags()
    if flags.disable_new_agent_stack or not flags.enable_action_log:
        raise HTTPException(
            status_code=503,
            detail=(
                "Action log is not available on this deployment. Flip "
                "SURFSENSE_ENABLE_ACTION_LOG to enable it."
            ),
        )


@router.get(
    "/threads/{thread_id}/actions",
    response_model=AgentActionListResponse,
)
async def list_thread_actions(
    thread_id: int,
    page: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> AgentActionListResponse:
    """List agent actions for a thread, newest first.

    Authorization:
    * Caller must be a member of the thread's search space with
      ``CHATS_READ`` permission.

    Pagination:
    * ``page`` is 0-indexed.
    * ``page_size`` defaults to 50, max 200.
    """

    _flag_guard()

    thread = await session.get(NewChatThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found.")

    await check_permission(
        session,
        user,
        thread.search_space_id,
        Permission.CHATS_READ.value,
        "You don't have permission to view this thread's action log.",
    )

    total_stmt = select(func.count(AgentActionLog.id)).where(
        AgentActionLog.thread_id == thread_id
    )
    total = (await session.execute(total_stmt)).scalar_one()

    rows_stmt = (
        select(AgentActionLog)
        .where(AgentActionLog.thread_id == thread_id)
        .order_by(AgentActionLog.created_at.desc(), AgentActionLog.id.desc())
        .offset(page * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(rows_stmt)).scalars().all()

    # Build a reverse_of -> revert_action_id map so the UI can render
    # "Reverted" badges on actions that have already been undone.
    if rows:
        original_ids = [r.id for r in rows]
        reverts_stmt = select(AgentActionLog.id, AgentActionLog.reverse_of).where(
            AgentActionLog.reverse_of.in_(original_ids)
        )
        reverts = (await session.execute(reverts_stmt)).all()
        revert_map: dict[int, int] = {orig: rev for rev, orig in reverts}
    else:
        revert_map = {}

    items = [
        AgentActionRead(
            id=row.id,
            thread_id=row.thread_id,
            user_id=str(row.user_id) if row.user_id is not None else None,
            search_space_id=row.search_space_id,
            tool_name=row.tool_name,
            args=row.args,
            result_id=row.result_id,
            reversible=bool(row.reversible),
            reverse_descriptor=row.reverse_descriptor,
            error=row.error,
            reverse_of=row.reverse_of,
            reverted_by_action_id=revert_map.get(row.id),
            is_revert_action=row.reverse_of is not None,
            tool_call_id=row.tool_call_id,
            chat_turn_id=row.chat_turn_id,
            created_at=row.created_at,
        )
        for row in rows
    ]

    return AgentActionListResponse(
        items=items,
        total=int(total),
        page=page,
        page_size=page_size,
        has_more=(page + 1) * page_size < int(total),
    )
