"""opencode as an agent engine: the thread's turns live in an opencode session in its folder."""

from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.agent_threads import live_instances, stored_step
from modules.agent.agent_threads.forget_sessions import (
    forget_thread,
    forget_workspace_sessions,
)
from modules.agent.agent_threads.open_session import open_agent_session
from modules.agent.agent_threads.thread_messages import agent_thread_messages
from modules.agent.agent_threads.turn import RunPlace, agent_turn
from modules.agent.opencode_client import OpencodeVersionError
from modules.agent.opencode_runtime import (
    AgentUnavailableError,
    connect_opencode,
    ready_opencode,
)
from modules.chat.models import AgentEngineKind, ChatThread
from modules.chat.schemas import MessageCreate
from shared.config import get_storage_settings


class OpencodeEngine:
    kind = AgentEngineKind.OPENCODE

    def has_session(self, thread: ChatThread) -> bool:
        return thread.opencode_session_id is not None

    async def ensure_session(
        self, session: Session, thread: ChatThread, launch_key: str
    ) -> None:
        if thread.opencode_session_id is not None:
            return
        try:
            ready = await ready_opencode(session, launch_key=launch_key)
        except (AgentUnavailableError, OpencodeVersionError) as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(error)
            ) from error
        folder = get_storage_settings().thread_working_dir(
            thread.workspace_id, thread.id
        )
        try:
            live_instances.instance_used(folder)
            session_id = await ready.client.create_session(
                folder, thread.title or "New chat", model=ready.model
            )
        except httpx.HTTPError as error:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
            ) from error
        finally:
            await ready.client.close()
        await transact(session, _record_session, thread, session_id)

    async def renew_session(self, session: Session, thread: ChatThread) -> bool:
        return False

    async def open_session(
        self, session: Session, thread: ChatThread, launch_key: str
    ) -> bool:
        session_id = await open_agent_session(session, thread, launch_key)
        if session_id is None:
            return False
        await transact(session, _record_session, thread, session_id)
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
        return await agent_turn(session, thread, payload, launch_key, place, handover)

    async def thread_messages(
        self, session: Session, thread: ChatThread, launch_key: str, answering: bool
    ) -> list[dict[str, Any]]:
        return await agent_thread_messages(session, thread, launch_key, answering)

    async def answer_permission(
        self, thread: ChatThread, request_id: str, reply: Literal["once", "reject"]
    ) -> None:
        """Pass the user's answer to the opencode session waiting on it."""
        try:
            client = connect_opencode()
        except AgentUnavailableError as error:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(error)
            ) from error
        session_id = thread.opencode_session_id
        if session_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such request is waiting")
        async with client:
            try:
                await client.reply(session_id, request_id, reply)
            except httpx.HTTPStatusError as error:
                if error.response.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND, "no such request is waiting"
                    ) from error
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, f"opencode refused the answer: {error}"
                ) from error
            except httpx.HTTPError as error:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
                ) from error

    async def stored_step(
        self, session: Session, thread: ChatThread, part_id: str
    ) -> dict[str, Any]:
        # A step goes by its call's id.
        return await stored_step.stored_step(thread, part_id)

    async def forget_thread(self, thread: ChatThread) -> Path:
        if thread.opencode_session_id is None:
            raise ValueError(f"thread {thread.id} is not the agent's")
        return await forget_thread(
            thread.workspace_id, thread.id, thread.opencode_session_id
        )

    def forget_workspace(self, session: Session, workspace_id: int) -> None:
        forget_workspace_sessions(session, workspace_id)


def _record_session(session: Session, thread: ChatThread, session_id: str) -> None:
    """Reloaded here, off the event loop: the write moves `updated_at`, which the response reads."""
    thread.agent_engine = AgentEngineKind.OPENCODE
    thread.opencode_session_id = session_id
    session.flush()
    session.refresh(thread)
