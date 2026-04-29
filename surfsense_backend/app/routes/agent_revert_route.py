"""POST ``/api/threads/{thread_id}/revert/{action_id}``: undo an agent action.

The route ships **before** the UI lights up the per-message "Undo from
here" affordance. To prevent accidental usage during the gap we return
``503 Service Unavailable`` until the ``SURFSENSE_ENABLE_REVERT_ROUTE``
flag flips. Once enabled, the route runs:

1. Authentication via :func:`current_active_user`.
2. Action lookup; 404 if the action does not belong to the thread.
3. Authorization via :func:`app.services.revert_service.can_revert`.
4. Revert dispatch via :func:`app.services.revert_service.revert_action`.
5. Idempotent on retries: if the same action is reverted twice the second
   call returns 409 ``"already reverted"``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.new_chat.feature_flags import get_flags
from app.db import (
    AgentActionLog,
    User,
    get_async_session,
)
from app.services.revert_service import (
    RevertOutcome,
    can_revert,
    load_action,
    load_thread,
    revert_action,
)
from app.users import current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/threads/{thread_id}/revert/{action_id}")
async def revert_agent_action(
    thread_id: int,
    action_id: int,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> dict:
    flags = get_flags()
    if flags.disable_new_agent_stack or not flags.enable_revert_route:
        raise HTTPException(
            status_code=503,
            detail=(
                "Revert is not available on this deployment yet. The route "
                "ships before the UI; flip SURFSENSE_ENABLE_REVERT_ROUTE to "
                "enable it."
            ),
        )

    thread = await load_thread(session, thread_id=thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found.")

    action = await load_action(session, action_id=action_id, thread_id=thread_id)
    if action is None:
        raise HTTPException(
            status_code=404,
            detail="Action not found or does not belong to this thread.",
        )

    # Idempotency: if a successful revert already exists, return 409.
    existing_revert = await session.execute(
        select(AgentActionLog).where(AgentActionLog.reverse_of == action.id)
    )
    if existing_revert.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="This action has already been reverted.",
        )

    if not can_revert(
        requester_user_id=str(user.id) if user is not None else None,
        action=action,
        is_admin=False,  # role lookup is done by RBAC layer; default conservative
    ):
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to revert this action.",
        )

    outcome: RevertOutcome
    try:
        outcome = await revert_action(
            session,
            action=action,
            requester_user_id=str(user.id) if user is not None else None,
        )
    except Exception as err:
        logger.exception("Revert dispatch raised for action_id=%s", action_id)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Internal error during revert."
        ) from err

    if outcome.status == "ok":
        await session.commit()
        return {
            "status": "ok",
            "message": outcome.message,
            "new_action_id": outcome.new_action_id,
        }

    await session.rollback()

    if outcome.status == "not_found" or outcome.status == "tool_unavailable":
        raise HTTPException(status_code=409, detail=outcome.message)
    if outcome.status == "permission_denied":
        raise HTTPException(status_code=403, detail=outcome.message)
    if outcome.status == "reverse_not_implemented":
        raise HTTPException(status_code=501, detail=outcome.message)
    # not_reversible
    raise HTTPException(status_code=409, detail=outcome.message)
