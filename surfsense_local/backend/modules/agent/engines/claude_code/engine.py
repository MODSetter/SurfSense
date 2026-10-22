"""Claude Code as an agent engine, for a thread on a Claude plan model.

The thread's turns live in its Claude Code session, which SurfSense keeps a
copy of; read back, they are shaped as opencode's, so the thread shows both
engines' turns alike (docs/architecture/claude-plan.md).
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Literal

from anyio import from_thread
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.agent_threads.citations import load_citations, searched_chunks
from modules.agent.agent_threads.ready_renders import link_ready_renders
from modules.agent.agent_threads.replies import reply_id, session_turns, thread_turns
from modules.agent.agent_threads.reply_ending import ABORTED
from modules.agent.agent_threads.scope_note import name_scopes
from modules.agent.agent_threads.turn import RunPlace
from modules.agent.engines.claude_code.agent_runs import AgentRuns
from modules.agent.engines.claude_code.approvals import APPROVALS
from modules.agent.engines.claude_code.endings import recorded_endings
from modules.agent.engines.claude_code.models import ClaudeSessionEntry
from modules.agent.engines.claude_code.session_files import delete_session_files
from modules.agent.engines.claude_code.skills_plugin import build_skills_plugin
from modules.agent.engines.claude_code.transcript_shape import opencode_messages
from modules.agent.engines.claude_code.turn import ClaudeSetup, claude_turn
from modules.agent.opencode_config import skills_folder
from modules.agent.thread_folder.layout import forget_thread_lock, fresh_thread_folder
from modules.chat.models import AgentEngineKind, ChatThread
from modules.chat.schemas import MessageCreate
from modules.llm.subscriptions.claude.locate import this_machines_claude
from modules.llm.subscriptions.claude.proxy import claude_proxy_url
from modules.llm.subscriptions.claude.status import signed_in_account
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)


class ClaudeCodeEngine:
    kind = AgentEngineKind.CLAUDE_CODE

    def has_session(self, thread: ChatThread) -> bool:
        return thread.claude_session_id is not None

    async def ensure_session(
        self, session: Session, thread: ChatThread, launch_key: str
    ) -> None:
        if thread.claude_session_id is None:
            await transact(session, _name_session, thread, str(uuid.uuid4()))

    async def renew_session(self, session: Session, thread: ChatThread) -> bool:
        """Another Claude account signed in since the session was made gets a session of its own.

        A session made before its account was read is taken as the one signed in now.
        """
        if thread.claude_session_id is None:
            return False
        account = await run_in_threadpool(
            signed_in_account, this_machines_claude(), proxy_url=claude_proxy_url()
        )
        if account is None or account == thread.claude_account:
            return False
        if thread.claude_account is None:
            await transact(session, _record_account, thread, account)
            return False
        left = thread.claude_session_id
        await self._runs.forget(thread.id)
        await transact(session, _renew_session, thread, str(uuid.uuid4()), account)
        # SurfSense's copy keeps its turns; Claude Code's own is not needed again.
        await run_in_threadpool(delete_session_files, left)
        return True

    def __init__(self) -> None:
        self._runs = AgentRuns()
        self._setup: ClaudeSetup | None = None
        self._building = asyncio.Lock()

    async def _ready_setup(self) -> ClaudeSetup:
        """Built once per run of the app, from the skills this version ships."""
        async with self._building:
            if self._setup is None:
                claude = get_storage_settings().data_dir / "claude"
                skills = await run_in_threadpool(
                    build_skills_plugin, skills_folder(), claude / "skills-plugin"
                )
                self._setup = ClaudeSetup(self._runs, skills, claude / "mcp")
        return self._setup

    async def open_session(
        self, session: Session, thread: ChatThread, launch_key: str
    ) -> bool:
        """Name the session the thread's turns will live in; Claude Code makes it on the first."""
        try:
            await run_in_threadpool(fresh_thread_folder, thread.workspace_id, thread.id)
        except OSError:
            logger.warning(
                "thread %s opens as a chat: its folder holds a deleted thread's files",
                thread.id,
                exc_info=True,
            )
            return False
        await transact(session, _record_session, thread, str(uuid.uuid4()))
        return True

    async def run_turn(
        self,
        session: Session,
        thread: ChatThread,
        payload: MessageCreate,
        launch_key: str,
        place: RunPlace,
        handover: str | None = None,
    ) -> StreamingResponse:
        setup = await self._ready_setup()
        return await claude_turn(
            session, thread, payload, launch_key, place, setup, handover
        )

    async def thread_messages(
        self, session: Session, thread: ChatThread, launch_key: str, answering: bool
    ) -> list[dict[str, Any]]:
        messages = await self._messages(session, thread)
        endings = await transact(session, recorded_endings, thread.id)
        _mark_endings(messages, endings, answering)
        citations = await transact(
            session, load_citations, thread.workspace_id, searched_chunks(messages)
        )
        turns = await run_in_threadpool(
            thread_turns, messages, citations, endings, answering
        )
        await transact(session, link_ready_renders, thread.workspace_id, turns)
        await transact(session, name_scopes, thread.workspace_id, turns)
        return turns

    async def answer_permission(
        self, thread: ChatThread, request_id: str, reply: Literal["once", "reject"]
    ) -> None:
        if not APPROVALS.answer(thread.id, request_id, reply):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such request is waiting")

    async def stored_step(
        self, session: Session, thread: ChatThread, part_id: str
    ) -> dict[str, Any]:
        for message in await self._messages(session, thread):
            for item in message.get("content") or []:
                if item.get("id") == part_id and item.get("type") == "tool":
                    return item
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such step in this thread")

    async def forget_thread(self, thread: ChatThread) -> Path:
        """End its Claude Code and delete Claude Code's own transcript; SurfSense's goes with the row."""
        folder = get_storage_settings().thread_working_dir(
            thread.workspace_id, thread.id
        )
        await self._forget(thread.id, thread.claude_session_id, folder)
        return folder

    def forget_workspace(self, session: Session, workspace_id: int) -> None:
        threads = session.execute(
            select(ChatThread.id, ChatThread.claude_session_id).where(
                ChatThread.workspace_id == workspace_id,
                # Not only the threads on Claude Code now: one that left keeps its session.
                ChatThread.claude_session_id.is_not(None),
            )
        ).all()
        storage = get_storage_settings()
        for thread_id, session_id in threads:
            folder = storage.thread_working_dir(workspace_id, thread_id)
            from_thread.run(self._forget, thread_id, session_id, folder)

    async def close(self) -> None:
        """Quit: end every running Claude Code."""
        await self._runs.close_all()

    async def _forget(
        self, thread_id: int, session_id: str | None, folder: Path
    ) -> None:
        APPROVALS.drop(thread_id)
        await self._runs.forget(thread_id)
        forget_thread_lock(folder)
        if session_id is not None:
            await run_in_threadpool(delete_session_files, session_id)

    async def _messages(
        self, session: Session, thread: ChatThread
    ) -> list[dict[str, Any]]:
        if thread.claude_session_id is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "this thread is not the agent's"
            )
        entries = await transact(session, _entries, thread.id)
        return opencode_messages(entries)


def _record_session(session: Session, thread: ChatThread, session_id: str) -> None:
    """Reloaded here, off the event loop: the write moves `updated_at`, which the response reads."""
    thread.agent_engine = AgentEngineKind.CLAUDE_CODE
    thread.claude_session_id = session_id
    session.flush()
    session.refresh(thread)


def _name_session(session: Session, thread: ChatThread, session_id: str) -> None:
    thread.claude_session_id = session_id
    session.flush()
    session.refresh(thread)


def _record_account(session: Session, thread: ChatThread, account: str) -> None:
    thread.claude_account = account


def _renew_session(
    session: Session, thread: ChatThread, session_id: str, account: str
) -> None:
    thread.claude_session_id = session_id
    thread.claude_account = account
    session.flush()
    session.refresh(thread)


def _entries(session: Session, thread_id: int) -> list[dict[str, Any]]:
    """Every session the thread had in Claude Code, one per account, in the order written."""
    return list(
        session.scalars(
            select(ClaudeSessionEntry.entry)
            .where(ClaudeSessionEntry.thread_id == thread_id)
            .order_by(ClaudeSessionEntry.id)
        )
    )


def _mark_endings(
    messages: list[dict[str, Any]], endings: dict[str, dict[str, Any]], answering: bool
) -> None:
    """A reply SurfSense noted as unfinished reads as opencode's aborted one does.

    The reply still being written is left alone: its ending is noted from its start.
    """
    turns = session_turns(messages)
    for index, turn in enumerate(turns):
        live = answering and index == len(turns) - 1
        if turn.steps and not live and reply_id(turn.user["id"]) in endings:
            turn.steps[-1]["error"] = {"type": ABORTED, "message": "Stopped"}
