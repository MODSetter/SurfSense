"""The SDK's SessionStore over SurfSense's database, for one thread's Claude Code session."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from modules.agent.engines.claude_code.models import ClaudeSessionEntry


class ThreadSessionStore:
    """Entries arrive in batches about every 100 ms while a turn runs; each is one short write."""

    def __init__(self, sessions: sessionmaker[Session], thread_id: int) -> None:
        self._sessions = sessions
        self._thread_id = thread_id

    async def append(self, key: dict[str, Any], entries: list[dict[str, Any]]) -> None:
        # A subagent's transcript is never the thread's, and SurfSense gives none.
        if key.get("subpath") or not entries:
            return
        await run_in_threadpool(self._append, key["session_id"], entries)

    async def load(self, key: dict[str, Any]) -> list[dict[str, Any]] | None:
        if key.get("subpath"):
            return None
        entries = await run_in_threadpool(self._load, key["session_id"])
        return entries or None

    def _append(self, session_id: str, entries: list[dict[str, Any]]) -> None:
        rows = [
            {
                "thread_id": self._thread_id,
                "session_id": session_id,
                "uuid": entry.get("uuid"),
                "entry": entry,
            }
            for entry in entries
        ]
        with self._sessions() as session:
            # The uuid is the SDK's idempotency key: a retried batch may have landed.
            session.execute(
                insert(ClaudeSessionEntry).values(rows).on_conflict_do_nothing()
            )
            session.commit()

    def _load(self, session_id: str) -> list[dict[str, Any]]:
        with self._sessions() as session:
            return list(
                session.scalars(
                    select(ClaudeSessionEntry.entry)
                    .where(ClaudeSessionEntry.session_id == session_id)
                    .order_by(ClaudeSessionEntry.id)
                )
            )
