"""A thread that switched engines lives in both their sessions; read back, it is one thread."""

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.agent.engines.thread_engine import every_engine, thread_engine
from modules.chat.models import ChatThread


async def thread_turns_of(
    session: Session, thread: ChatThread, launch_key: str, answering: bool
) -> list[dict[str, Any]]:
    """Every engine's turns, each with its reply, oldest first.

    Only the engine running the thread now can be writing its latest reply.
    """
    current = thread_engine(thread)
    pairs: list[list[dict[str, Any]]] = []
    for engine in every_engine():
        if not engine.has_session(thread):
            continue
        live = answering and engine is current
        turns = await engine.thread_messages(session, thread, launch_key, live)
        pairs += _pairs(turns)
    pairs.sort(key=lambda pair: pair[0]["created_at"] or "")
    return [turn for pair in pairs for turn in pair]


async def stored_step_of(
    session: Session, thread: ChatThread, part_id: str
) -> dict[str, Any]:
    """The step from whichever engine's session holds it."""
    for engine in every_engine():
        if not engine.has_session(thread):
            continue
        try:
            return await engine.stored_step(session, thread, part_id)
        except HTTPException as refused:
            if refused.status_code != status.HTTP_404_NOT_FOUND:
                raise
    raise HTTPException(status.HTTP_404_NOT_FOUND, "no such step in this thread")


def _pairs(turns: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    pairs: list[list[dict[str, Any]]] = []
    for turn in turns:
        if turn["role"] == "user" or not pairs:
            pairs.append([turn])
        else:
            pairs[-1].append(turn)
    return pairs
