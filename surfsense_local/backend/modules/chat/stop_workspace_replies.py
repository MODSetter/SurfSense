import asyncio

from anyio import from_thread
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.chat.models import ChatThread
from modules.chat.runs.registry import STOP_SETTLE_SECONDS, ChatRuns


def stop_workspace_replies(session: Session, runs: ChatRuns, workspace_id: int) -> None:
    """Stop every reply in the workspace before it is deleted.

    Called from the workspace route, which runs in a worker thread. The
    session's write lock is let go first, or no reply could store its end.
    """
    thread_ids = session.scalars(
        select(ChatThread.id).where(ChatThread.workspace_id == workspace_id)
    ).all()
    answering = runs.running().intersection(thread_ids)
    if not answering:
        return
    session.commit()
    from_thread.run(_stop_all, runs, answering)


async def _stop_all(runs: ChatRuns, thread_ids: frozenset[int]) -> None:
    await asyncio.gather(
        *(runs.stop(thread_id, STOP_SETTLE_SECONDS) for thread_id in thread_ids)
    )
