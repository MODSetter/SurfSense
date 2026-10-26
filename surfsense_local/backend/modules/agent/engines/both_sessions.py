"""A thread that switched engines lives in both their sessions; read back, it is one thread.

The engine the thread left may not answer now (opencode not running): its turns are
left out, with a warning, rather than the thread unreadable. The engine running the
thread is never skipped, since its turns are the latest.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.agent.engines.agent_engine import AgentEngine
from modules.chat.models import ChatThread

logger = logging.getLogger(__name__)


async def thread_turns_of(
    session: Session,
    thread: ChatThread,
    launch_key: str,
    answering: bool,
    engines: Sequence[AgentEngine],
) -> list[dict[str, Any]]:
    """Every engine's turns, each with its reply, oldest first.

    Only the engine running the thread now can be writing its latest reply.
    """
    pairs: list[list[dict[str, Any]]] = []
    for engine in engines:
        if not engine.has_session(thread):
            continue
        current = engine.kind is thread.agent_engine
        live = answering and current
        try:
            turns = await engine.thread_messages(session, thread, launch_key, live)
        except HTTPException as refused:
            if current:
                raise
            _left_out(engine, thread, refused)
            continue
        pairs += _pairs(turns)
    pairs.sort(key=lambda pair: _sent_at(pair[0]["created_at"]))
    return [turn for pair in pairs for turn in pair]


def _sent_at(created_at: str | None) -> datetime:
    """By time, not text: a whole second is spelled without its fraction, which sorts after one."""
    if created_at is None:
        return datetime.min.replace(tzinfo=UTC)
    return datetime.fromisoformat(created_at)


async def stored_step_of(
    session: Session,
    thread: ChatThread,
    part_id: str,
    engines: Sequence[AgentEngine],
) -> dict[str, Any]:
    """The step from whichever engine's session holds it."""
    for engine in engines:
        if not engine.has_session(thread):
            continue
        try:
            return await engine.stored_step(session, thread, part_id)
        except HTTPException as refused:
            if refused.status_code == status.HTTP_404_NOT_FOUND:
                continue
            if engine.kind is thread.agent_engine:
                raise
            _left_out(engine, thread, refused)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "no such step in this thread")


def _left_out(engine: AgentEngine, thread: ChatThread, refused: HTTPException) -> None:
    logger.warning(
        "thread %s read without its %s session, which did not answer: %s",
        thread.id,
        engine.kind,
        refused.detail,
    )


def _pairs(turns: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    pairs: list[list[dict[str, Any]]] = []
    for turn in turns:
        if turn["role"] == "user" or not pairs:
            pairs.append([turn])
        else:
            pairs[-1].append(turn)
    return pairs
