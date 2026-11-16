"""SurfSense's copy of a thread's Claude Code session, and how its replies ended.

Claude Code deletes its own transcripts after 30 days, and the user owns
~/.claude, so the thread lives here (docs/architecture/claude-plan.md, Sessions).
"""

from typing import Any

from sqlalchemy import JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base


class ClaudeSessionEntry(Base):
    """One transcript line, in the order Claude Code wrote it."""

    __tablename__ = "claude_session_entries"
    __table_args__ = (
        # A retried batch lands again; an entry without a uuid is always kept.
        Index("claude_session_entries_session_uuid", "session_id", "uuid", unique=True),
        Index("claude_session_entries_thread", "thread_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE")
    )
    session_id: Mapped[str]
    uuid: Mapped[str | None]
    entry: Mapped[dict[str, Any]] = mapped_column(JSON)


class ClaudeReplyEnding(Base):
    """A reply that did not finish: stopped, failed, or cut off when the app went away."""

    __tablename__ = "claude_reply_endings"

    thread_id: Mapped[int] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), primary_key=True
    )
    reply_id: Mapped[str] = mapped_column(primary_key=True)
    ending: Mapped[dict[str, Any]] = mapped_column(JSON)
