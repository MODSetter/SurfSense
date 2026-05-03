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

This module also hosts the per-turn batch endpoint
``POST /api/threads/{thread_id}/revert-turn/{chat_turn_id}``. It
walks every reversible action emitted during a chat turn in reverse
``created_at`` order and reverts each independently. Partial success is the
common case — the response always contains a per-action result list and a
``status`` of ``"ok"`` or ``"partial"``; we never collapse the batch into a
whole-batch 4xx.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    except IntegrityError:
        # Partial unique index ``ux_agent_action_log_reverse_of`` caught
        # a concurrent revert. Translate to the existing 409 "already
        # reverted" contract so racing clients see consistent
        # behaviour with the pre-flight TOCTOU check above.
        await session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This action has already been reverted.",
        ) from None
    except Exception as err:
        logger.exception("Revert dispatch raised for action_id=%s", action_id)
        await session.rollback()
        raise HTTPException(
            status_code=500, detail="Internal error during revert."
        ) from err

    if outcome.status == "ok":
        try:
            await session.commit()
        except IntegrityError:
            # Race lost on commit (constraint enforced at flush in some
            # configs but at commit in others — defensive).
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail="This action has already been reverted.",
            ) from None
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


# ---------------------------------------------------------------------------
# Per-turn revert batch endpoint
# ---------------------------------------------------------------------------


PerActionStatus = Literal[
    "reverted",
    "already_reverted",
    "not_reversible",
    "permission_denied",
    "failed",
    "skipped",
]


class RevertTurnActionResult(BaseModel):
    """Per-action outcome inside a ``revert-turn`` batch response."""

    action_id: int
    tool_name: str
    status: PerActionStatus
    message: str | None = None
    new_action_id: int | None = None
    error: str | None = None


class RevertTurnResponse(BaseModel):
    """Top-level response for ``POST /threads/{id}/revert-turn/{chat_turn_id}``.

    ``status`` is ``"ok"`` only when every reversible row succeeded. Any
    ``failed`` / ``not_reversible`` / ``permission_denied`` entry downgrades
    it to ``"partial"``. Empty turns (no rows) return ``"ok"`` with an empty
    ``results`` list — callers should treat that as a no-op.

    Counter invariant:
        ``total == reverted + already_reverted + not_reversible
                  + permission_denied + failed + skipped``

    Frontend toasts and the ``RevertTurnButton`` summary rely on this
    invariant to display "X of Y reverted, Z could not be undone" without
    silently dropping ``permission_denied`` or ``skipped`` rows.
    """

    status: Literal["ok", "partial"]
    chat_turn_id: str
    total: int
    reverted: int
    already_reverted: int
    not_reversible: int
    permission_denied: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[RevertTurnActionResult]


def _classify_outcome(outcome: RevertOutcome) -> PerActionStatus:
    if outcome.status == "ok":
        return "reverted"
    if outcome.status == "permission_denied":
        return "permission_denied"
    # ``not_found`` / ``tool_unavailable`` / ``reverse_not_implemented`` /
    # ``not_reversible`` are all surfaced to the caller as "not_reversible"
    # — they share the same UX (this row cannot be undone) and only the
    # ``message`` differs.
    return "not_reversible"


async def _was_already_reverted(session: AsyncSession, *, action_id: int) -> int | None:
    """Return the id of an existing successful revert row, if any.

    Single-action variant — kept for the post-IntegrityError lookup
    path where we already know we lost a race for one specific id.
    """
    stmt = select(AgentActionLog.id).where(AgentActionLog.reverse_of == action_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def _was_already_reverted_batch(
    session: AsyncSession, *, action_ids: list[int]
) -> dict[int, int]:
    """Batch idempotency probe for the revert-turn loop.

    Replaces N individual ``SELECT id WHERE reverse_of = :id`` queries
    (one per row in the turn) with a single ``SELECT id, reverse_of
    WHERE reverse_of IN (:ids)``. The route still iterates rows in
    reverse-chronological order, but the membership check is O(1) per
    iteration after this query. For a turn with 30 actions that's 30
    fewer round-trips through asyncpg + a smaller transaction footprint.

    Returns a ``{original_action_id -> revert_action_id}`` map. Missing
    keys mean "not yet reverted" — callers should treat them as
    eligible for revert.
    """
    if not action_ids:
        return {}
    stmt = select(AgentActionLog.id, AgentActionLog.reverse_of).where(
        AgentActionLog.reverse_of.in_(action_ids)
    )
    result = await session.execute(stmt)
    return {
        original_id: revert_id
        for revert_id, original_id in result.all()
        if original_id is not None
    }


@router.post(
    "/threads/{thread_id}/revert-turn/{chat_turn_id}",
    response_model=RevertTurnResponse,
)
async def revert_agent_turn(
    thread_id: int,
    chat_turn_id: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
) -> RevertTurnResponse:
    """Revert every reversible action emitted during ``chat_turn_id``.

    Walks ``AgentActionLog`` rows for the turn in reverse ``created_at``
    order so dependencies (e.g. ``mkdir`` -> ``write_file`` inside the new
    folder) unwind in the right sequence. Each action is reverted in its
    own SAVEPOINT so a single failure does not poison the batch.

    Partial success is intentional and returned with HTTP 200. Callers
    must inspect ``results[*].status`` to find rows that need attention.
    """

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

    # Reverse-chronological so the latest mutation in the turn unwinds
    # first. ``id.desc()`` is the deterministic tiebreaker for actions
    # written in the same millisecond.
    rows_stmt = (
        select(AgentActionLog)
        .where(
            AgentActionLog.thread_id == thread_id,
            AgentActionLog.chat_turn_id == chat_turn_id,
        )
        .order_by(AgentActionLog.created_at.desc(), AgentActionLog.id.desc())
    )
    rows = (await session.execute(rows_stmt)).scalars().all()

    requester_user_id = str(user.id) if user is not None else None
    results: list[RevertTurnActionResult] = []
    # Counters MUST be exhaustive so the response invariant
    # ``total == sum(counters)`` always holds. Frontend toasts and
    # ``RevertTurnButton`` rely on this for "X of Y reverted" math.
    counts: dict[str, int] = {
        "reverted": 0,
        "already_reverted": 0,
        "not_reversible": 0,
        "permission_denied": 0,
        "failed": 0,
        "skipped": 0,
    }

    # Single batched idempotency probe replaces the previous per-row
    # SELECT. ``rows`` are filtered in the loop so we pre-collect only
    # the original-action ids (skip rows that are themselves
    # reverts).
    eligible_ids = [r.id for r in rows if r.reverse_of is None]
    already_reverted_map = await _was_already_reverted_batch(
        session, action_ids=eligible_ids
    )

    for action in rows:
        # Skip rows that ARE reverts of an earlier action — reverting a
        # revert is meaningless inside a batch (the user wants to wipe
        # the original effects, not chase tail).
        if action.reverse_of is not None:
            counts["skipped"] += 1
            results.append(
                RevertTurnActionResult(
                    action_id=action.id,
                    tool_name=action.tool_name,
                    status="skipped",
                    message="Row is itself a revert action; skipped.",
                )
            )
            continue

        # Idempotency: surface "already_reverted" instead of failing.
        existing_revert_id = already_reverted_map.get(action.id)
        if existing_revert_id is not None:
            counts["already_reverted"] += 1
            results.append(
                RevertTurnActionResult(
                    action_id=action.id,
                    tool_name=action.tool_name,
                    status="already_reverted",
                    new_action_id=existing_revert_id,
                )
            )
            continue

        if not can_revert(
            requester_user_id=requester_user_id,
            action=action,
            is_admin=False,
        ):
            counts["permission_denied"] += 1
            results.append(
                RevertTurnActionResult(
                    action_id=action.id,
                    tool_name=action.tool_name,
                    status="permission_denied",
                    message="You are not allowed to revert this action.",
                )
            )
            continue

        # Per-row SAVEPOINT so one failed revert never poisons later
        # successful ones.
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
            results.append(
                RevertTurnActionResult(
                    action_id=action.id,
                    tool_name=action.tool_name,
                    status=classified,
                    message=outcome.message,
                )
            )
            continue
        except IntegrityError:
            # Partial unique index caught a concurrent revert that won
            # the race against our pre-flight ``_was_already_reverted``
            # SELECT. Look up the winner so
            # we can surface its ``new_action_id`` to the client.
            existing_revert_id = await _was_already_reverted(
                session, action_id=action.id
            )
            counts["already_reverted"] += 1
            results.append(
                RevertTurnActionResult(
                    action_id=action.id,
                    tool_name=action.tool_name,
                    status="already_reverted",
                    new_action_id=existing_revert_id,
                )
            )
            continue
        except Exception as err:  # pragma: no cover — defensive, logged
            logger.exception(
                "Unexpected revert failure inside batch for action_id=%s",
                action.id,
            )
            counts["failed"] += 1
            results.append(
                RevertTurnActionResult(
                    action_id=action.id,
                    tool_name=action.tool_name,
                    status="failed",
                    error=str(err) or err.__class__.__name__,
                )
            )
            continue

        counts["reverted"] += 1
        results.append(
            RevertTurnActionResult(
                action_id=action.id,
                tool_name=action.tool_name,
                status="reverted",
                message=outcome.message,
                new_action_id=outcome.new_action_id,
            )
        )

    # Single commit at the end — successful SAVEPOINTs above already
    # released; failed ones rolled back to their savepoint. No row leaks
    # across the boundary.
    try:
        await session.commit()
    except Exception as err:  # pragma: no cover — defensive
        logger.exception(
            "Final commit for revert-turn failed (thread=%s turn=%s)",
            thread_id,
            chat_turn_id,
        )
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal error while finalising revert-turn batch.",
        ) from err

    has_partial = (
        counts["failed"] > 0
        or counts["not_reversible"] > 0
        or counts["permission_denied"] > 0
    )
    overall_status: Literal["ok", "partial"] = "partial" if has_partial else "ok"

    return RevertTurnResponse(
        status=overall_status,
        chat_turn_id=chat_turn_id,
        total=len(rows),
        reverted=counts["reverted"],
        already_reverted=counts["already_reverted"],
        not_reversible=counts["not_reversible"],
        permission_denied=counts["permission_denied"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        results=results,
    )


class _OutcomeRollbackError(Exception):
    """Sentinel raised inside the SAVEPOINT to roll back a non-OK outcome.

    ``revert_action`` writes a new ``agent_action_log`` row only on the
    happy path, but on the failure paths it sometimes mutates the
    ``DocumentRevision``/``Document`` tables before deciding the action
    is not reversible. Wrapping each call in ``begin_nested`` and raising
    this from the failure branch ensures we always discard partial
    writes for failed rows.
    """

    def __init__(self, outcome: RevertOutcome) -> None:
        self.outcome = outcome
        super().__init__(outcome.message)


__all__ = ["router"]
