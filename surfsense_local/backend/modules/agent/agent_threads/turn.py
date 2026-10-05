"""One turn of an agent thread, streamed in the chat's own frames.

opencode holds the turn; this sends the message, relays what the session does
until it is idle, then states the reply as opencode stored it. Closing the
stream stops the turn: nothing works on unseen.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import anyio
import httpx
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.agent_threads import live_instances
from modules.agent.agent_threads.citations import load_citations, searched_chunks
from modules.agent.agent_threads.legacy_thread import LEGACY_TURN, is_legacy
from modules.agent.agent_threads.ready_renders import link_live_render
from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.agent_threads.turn_sources import TurnSources, turn_sources
from modules.agent.engine_choice import selected_model_can_run_agent
from modules.agent.opencode_client import OpencodeVersionError
from modules.agent.opencode_runtime import (
    AgentUnavailableError,
    ReadyAgent,
    ready_opencode,
)
from modules.agent.thread_folder.sync import ThreadGoneError, sync_thread_folder
from modules.agent.tool_endpoint.failed_renders import begin_turn
from modules.agent.tool_endpoint.registration import register_thread_tools
from modules.chat.models import ChatThread
from modules.chat.schemas import MessageCreate
from modules.llm.resolution import ModelResolutionError
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

# A dropped or silent event stream is reopened; this many failures in a row
# means opencode is gone rather than restarting.
RECONNECTS = 20
_RECONNECT_SECONDS = 0.5
# As long as a chat title runs before it is cut, so a thread reads the same in the list.
TITLE_CHARS = 60
_DONE = b"data: [DONE]\n\n"


@dataclass(frozen=True)
class _Sending:
    """The user's words, the sources the turn works from, and the thread's new name if any."""

    text: str
    sources: TurnSources
    title: str | None


async def agent_turn(
    session: Session, thread: ChatThread, payload: MessageCreate, launch_key: str
) -> StreamingResponse:
    """Start the turn and answer with its stream, or refuse before anything is sent."""
    session_id = thread.opencode_session_id
    if session_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    if payload.images:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The agent does not read attached images yet. Send the text alone.",
        )
    # Stored and resolved in one transaction, as a chat's scope is, so a tick cannot race a send.
    sources = await transact(session, turn_sources, thread, payload)
    try:
        ready = await ready_opencode(session, launch_key=launch_key)
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except (AgentUnavailableError, OpencodeVersionError) as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    try:
        await _refuse_a_legacy_thread(ready, thread, session_id)
        # Checked once the model resolves, so a thread left with no model still asks for one.
        if not await selected_model_can_run_agent(session):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "The selected model cannot run the agent. Choose another model, "
                "or start a new chat to use this one.",
            )
        title = _first_title(thread, payload.text)
        if title is not None:
            await transact(session, _rename, thread, title)
    except BaseException:
        await ready.client.close()
        raise
    sending = _Sending(payload.text, sources, title)
    return StreamingResponse(
        _stream(session, thread, ready, launch_key, session_id, sending),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream(
    session: Session,
    thread: ChatThread,
    ready: ReadyAgent,
    launch_key: str,
    session_id: str,
    sending: _Sending,
) -> AsyncIterator[bytes]:
    """The turn's frames, from its sources prepared to the reply stored."""
    title = sending.title
    client = ready.client
    workspace_id = thread.workspace_id
    folder = get_storage_settings().thread_working_dir(workspace_id, thread.id)
    turn = TurnFrames(session_id)
    sent = False
    live_instances.turn_began(folder)
    try:
        # A big scope's first sync takes about 30 s: the thread says why it waits.
        count = len(sending.sources.document_ids)
        yield _frame({"type": "agent-preparing", "count": count})
        try:
            # Commits its own short reads: files are written with the write lock free.
            await run_in_threadpool(
                sync_thread_folder, session, thread, sending.sources.document_ids
            )
        except (ThreadGoneError, OSError) as error:
            logger.warning(
                "thread %s's sources were not prepared", thread.id, exc_info=True
            )
            yield _frame(_not_prepared(error))
            yield _DONE
            return
        await register_thread_tools(client, folder, workspace_id, thread.id, launch_key)
        begin_turn(thread.id)
        if sending.sources.shown is not None:
            # First, so the turn shows what the server resolved, not what the client guessed.
            yield _frame({"type": "agent-scope", "scope": sending.sources.shown})
        failures = 0
        while not turn.finished:
            try:
                async for event in client.events(folder):
                    failures = 0
                    if event.type == "server.connected":
                        # Opened before sending, so not one of the turn's events is missed.
                        if not sent:
                            await client.send_turn(
                                folder,
                                session_id,
                                sending.text,
                                model=ready.model,
                                note=sending.sources.note,
                            )
                            sent = True
                        elif await client.status(folder, session_id) == "idle":
                            turn.finished = True  # it ended while the stream was down
                            break
                        continue
                    for frame in turn.frames(event):
                        if frame.get("artifact") is not None:
                            # Whether it made the document, as the stored step says.
                            await transact(
                                session, link_live_render, workspace_id, frame
                            )
                        yield _frame(frame)
                        # After `accepted`, as the chat sends it: the thread exists to be renamed.
                        if frame["type"] == "accepted" and title is not None:
                            yield _frame(
                                {"type": "thread-title-update", "title": title}
                            )
                    if turn.finished:
                        break
            except httpx.HTTPError:
                failures += 1
                if not sent or failures >= RECONNECTS:
                    raise
                await asyncio.sleep(_RECONNECT_SECONDS)

        reply = None
        if turn.user_message_id is not None:
            messages = await client.messages(folder, session_id)
            citations = await transact(
                session, load_citations, workspace_id, searched_chunks(messages)
            )
            reply = turn_reply(messages, turn.user_message_id, citations)
        if reply and reply["content"]["citations"]:
            yield _frame({"type": "citations", "items": reply["content"]["citations"]})
        yield _frame(
            {
                "type": "completed",
                "assistant_completed_at": reply["completed_at"] if reply else None,
                "text": reply["content"]["text"] if reply else "",
            }
        )
        yield _DONE
    except httpx.HTTPError as failure:
        logger.warning("agent turn in %s failed", session_id, exc_info=True)
        message = f"The agent could not be reached: {failure}"
        yield _frame(
            {
                "type": "error",
                "kind": "network",
                "message": message,
                "provider": "opencode",
            }
        )
        yield _DONE
    finally:
        # Starlette cancels this when the client hangs up: the turn stops with it.
        with anyio.CancelScope(shield=True):
            if sent and not turn.finished:
                try:
                    await client.abort(folder, session_id)
                except httpx.HTTPError:
                    logger.warning(
                        "could not stop agent turn in %s", session_id, exc_info=True
                    )
            await live_instances.turn_ended(client, folder)
            await client.close()


def _not_prepared(error: Exception) -> dict:
    """The error frame for a turn whose sources could not be put in its folder."""
    message = (
        "This chat was deleted."
        if isinstance(error, ThreadGoneError)
        else f"The chat's sources could not be prepared: {error}"
    )
    return {
        "type": "error",
        "kind": "unknown",
        "message": message,
        "provider": "opencode",
    }


async def _refuse_a_legacy_thread(
    ready: ReadyAgent, thread: ChatThread, session_id: str
) -> None:
    """A thread whose session works in the folder all threads once shared is only read back."""
    folder = get_storage_settings().thread_working_dir(thread.workspace_id, thread.id)
    try:
        legacy = await is_legacy(ready.client, session_id, folder)
    except httpx.HTTPStatusError as error:
        # Gone from opencode: no turn can continue it, as with a legacy thread.
        if error.response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status.HTTP_409_CONFLICT, LEGACY_TURN) from error
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
        ) from error
    except httpx.HTTPError as error:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"opencode did not answer: {error}"
        ) from error
    if legacy:
        raise HTTPException(status.HTTP_409_CONFLICT, LEGACY_TURN)


def _first_title(thread: ChatThread, text: str) -> str | None:
    """A name for a thread still called "New chat", from its first message."""
    if (thread.title or "").casefold() != "new chat":
        return None
    words = " ".join(text.split())
    return (
        words if len(words) <= TITLE_CHARS else words[: TITLE_CHARS - 1].rstrip() + "…"
    )


def _rename(_session: Session, thread: ChatThread, title: str) -> None:
    """Store the thread's new name."""
    thread.title = title


def _frame(payload: dict) -> bytes:
    """One SSE data frame, as the chat stream spells them."""
    return f"data: {json.dumps(payload)}\n\n".encode()
