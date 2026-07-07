"""The durable checkpointer survives Celery's fresh-loop-per-task model.

Slice 1's whole point: the shared ``AsyncPostgresSaver`` pool binds connections
to the loop that opened them, and Celery runs each task on a new loop. This
writes a checkpoint on one ``run_async_celery_task`` loop and reads it back on a
*fresh* one — proving the per-task pool dispose lets a new loop reopen and read
committed state, rather than stalling on a stale connection.

Uses the real pool against the real (test) Postgres, so a regression in the
dispose wiring fails here, not just in production.
"""

from __future__ import annotations

import uuid

import pytest
from langgraph.checkpoint.base import empty_checkpoint

from app.agents.chat.runtime.checkpointer import close_checkpointer, get_checkpointer
from app.tasks.celery_tasks import run_async_celery_task

pytestmark = pytest.mark.integration


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}


def test_checkpoint_written_on_one_loop_is_readable_on_a_fresh_loop() -> None:
    thread_id = f"cross-loop-{uuid.uuid4()}"
    config = _config(thread_id)
    checkpoint = empty_checkpoint()

    async def _write() -> None:
        cp = await get_checkpointer()
        await cp.aput(config, checkpoint, {"source": "update", "step": 0}, {})

    async def _read():
        cp = await get_checkpointer()
        return await cp.aget_tuple(config)

    async def _cleanup() -> None:
        cp = await get_checkpointer()
        delete = getattr(cp, "adelete_thread", None)
        if delete is not None:
            await delete(thread_id)

    # Loop 1 writes and commits; run_async_celery_task disposes the pool after.
    run_async_celery_task(_write)

    # Loop 2 is a brand-new event loop: a stale loop-bound pool would stall
    # here (PoolTimeout). It must reopen and read the committed checkpoint.
    tup = run_async_celery_task(_read)

    try:
        assert tup is not None, "fresh loop could not read the prior checkpoint"
        assert tup.checkpoint["id"] == checkpoint["id"]
    finally:
        run_async_celery_task(_cleanup)
        run_async_celery_task(lambda: close_checkpointer())
