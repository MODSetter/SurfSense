"""How a Claude Code reply ended when it did not finish, which only SurfSense knows."""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from modules.agent.engines.claude_code.models import ClaudeReplyEnding

# Kept from a turn's start, so a reply cut off by the app going away reads as such.
INTERRUPTED = {"type": "interrupted"}
STOPPED = {"type": "stopped"}


def record_ending(
    session: Session, thread_id: int, reply_id: str, ending: dict[str, Any]
) -> None:
    session.execute(
        insert(ClaudeReplyEnding)
        .values(thread_id=thread_id, reply_id=reply_id, ending=ending)
        .on_conflict_do_update(
            index_elements=["thread_id", "reply_id"], set_={"ending": ending}
        )
    )


def finished(session: Session, thread_id: int, reply_id: str) -> None:
    """The reply completed: it keeps no ending."""
    session.execute(
        delete(ClaudeReplyEnding).where(
            ClaudeReplyEnding.thread_id == thread_id,
            ClaudeReplyEnding.reply_id == reply_id,
        )
    )


def recorded_endings(session: Session, thread_id: int) -> dict[str, dict[str, Any]]:
    """Every unfinished reply's ending, by reply id."""
    rows = session.execute(
        select(ClaudeReplyEnding.reply_id, ClaudeReplyEnding.ending).where(
            ClaudeReplyEnding.thread_id == thread_id
        )
    )
    return dict(rows.tuples().all())
