"""One turn of an agent thread, run in the background in the chat's own frames.

opencode holds the turn; this sends the message, relays what the session does
until it is idle, then states the reply as opencode stored it. The turn is a
run: a window that hangs up stops following it, not the turn; Stop and quit
end it.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import anyio
import httpx
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.agent_threads import live_instances
from modules.agent.agent_threads.citations import load_citations, searched_chunks
from modules.agent.agent_threads.legacy_thread import LEGACY_TURN, is_legacy
from modules.agent.agent_threads.ready_renders import link_live_render
from modules.agent.agent_threads.recorded_endings import record_ending
from modules.agent.agent_threads.replies import reply_id, turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.agent_threads.turn_sources import TurnSources, turn_sources
from modules.agent.engine_choice import selected_model_can_run_agent
from modules.agent.opencode_client import OpencodeClient, OpencodeVersionError
from modules.agent.opencode_runtime import (
    AgentUnavailableError,
    ReadyAgent,
    ready_opencode,
)
from modules.agent.thread_folder.sync import ThreadGoneError, sync_thread_folder
from modules.agent.tool_endpoint.failed_renders import begin_turn
from modules.agent.tool_endpoint.registration import register_thread_tools
from modules.chat.errors import classify_chat_error
from modules.chat.models import ChatThread
from modules.chat.runs.notify import notify_run
from modules.chat.runs.registry import ChatRuns
from modules.chat.runs.run import Run, RunState
from modules.chat.runs.stream import event_stream
from modules.chat.schemas import MessageCreate
from modules.events.broker import EventBroker
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


@dataclass(frozen=True)
class RunPlace:
    """What a turn needs to run past its request: the registry, its own sessions,
    and the broker that tells every window."""

    runs: ChatRuns
    session_factory: sessionmaker[Session]
    broker: EventBroker


async def agent_turn(
    session: Session,
    thread: ChatThread,
    payload: MessageCreate,
    launch_key: str,
    place: RunPlace,
) -> StreamingResponse:
    """Start the turn as a run and follow it, or refuse before anything is sent."""
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
    thread_id, workspace_id = thread.id, thread.workspace_id

    async def frames(run: Run) -> AsyncIterator[bytes]:
        # The run outlives this request, so it keeps its own session.
        with place.session_factory() as run_session:
            async for frame in _stream(
                run,
                run_session,
                (workspace_id, thread_id),
                ready,
                launch_key,
                session_id,
                sending,
            ):
                yield frame

    async def ended() -> None:
        notify_run(place.broker, workspace_id, thread_id, "done")

    def moved(state: RunState) -> None:
        notify_run(place.broker, workspace_id, thread_id, state.state)

    run = place.runs.start(thread_id, frames, on_end=ended, on_state=moved)
    notify_run(place.broker, workspace_id, thread_id, "running")
    # This request only follows the run: hanging up leaves the turn going.
    return event_stream(run.follow())


async def _stream(
    run: Run,
    session: Session,
    where: tuple[int, int],
    ready: ReadyAgent,
    launch_key: str,
    session_id: str,
    sending: _Sending,
) -> AsyncIterator[bytes]:
    """The turn's frames, from its sources prepared to the reply stored."""
    title = sending.title
    client = ready.client
    workspace_id, thread_id = where
    thread = await transact(session, _reload, thread_id)
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    turn = TurnFrames(session_id)
    # Approvals asked and not yet answered: the turn waits on the user meanwhile.
    waiting: set[str] = set()
    sent = False
    live_instances.turn_began(folder)
    try:
        # A big scope's first sync takes about 30 s: the thread says why it waits.
        count = len(sending.sources.document_ids)
        yield _frame({"type": "agent-preparing", "count": count})
        try:
            if thread is None:
                raise ThreadGoneError(thread_id)
            # Commits its own short reads: files are written with the write lock free.
            await run_in_threadpool(
                sync_thread_folder, session, thread, sending.sources.document_ids
            )
        except (ThreadGoneError, OSError) as error:
            logger.warning(
                "thread %s's sources were not prepared", thread_id, exc_info=True
            )
            yield _frame(_not_prepared(error))
            yield _DONE
            return
        # The turn's first call into its instance: one being disposed is finished first.
        await live_instances.wait_for_disposal(folder)
        await register_thread_tools(client, folder, workspace_id, thread_id, launch_key)
        begin_turn(thread_id)
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
                        _follow_approvals(run, waiting, frame)
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
    # The headers are sent: only a frame can tell the chat the turn ended.
    except Exception as failure:
        logger.exception("agent turn in %s failed", session_id)
        kind, message = classify_chat_error(failure, "opencode")
        yield _frame(
            {"type": "error", "kind": kind, "message": message, "provider": "opencode"}
        )
        yield _DONE
    finally:
        # Stop and quit cancel the run: the turn stops with it.
        with anyio.CancelScope(shield=True):
            if run.stop_requested and not turn.finished:
                # opencode stores a Stop as it stores a quit: only this note tells them apart.
                await _note_stop(client, folder, session_id, turn.user_message_id)
            if sent and not turn.finished:
                try:
                    await client.abort(folder, session_id)
                except httpx.HTTPError:
                    logger.warning(
                        "could not stop agent turn in %s", session_id, exc_info=True
                    )
            await live_instances.turn_ended(client, folder)
            await client.close()


async def _note_stop(
    client: OpencodeClient, folder: Path, session_id: str, user_message_id: str | None
) -> None:
    """Keep that the user stopped the reply; a failed write reads as interrupted,
    which offers Retry rather than hiding it."""
    if user_message_id is None:
        return
    try:
        await record_ending(
            client, folder, session_id, reply_id(user_message_id), {"type": "stopped"}
        )
    except httpx.HTTPError:
        logger.warning("could not note the stop of %s's reply", session_id)


def _follow_approvals(run: Run, waiting: set[str], frame: dict) -> None:
    """Say the run needs approval while any request waits, and running once none does."""
    if frame["type"] == "permission-request":
        waiting.add(frame["id"])
    elif frame["type"] == "permission-replied":
        waiting.discard(frame["id"])
    else:
        return
    run.set_state(RunState("needs-approval" if waiting else "running"))


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


def _reload(session: Session, thread_id: int) -> ChatThread | None:
    """The thread in the run's own session; None once it was deleted."""
    return session.get(ChatThread, thread_id)


def _rename(_session: Session, thread: ChatThread, title: str) -> None:
    """Store the thread's new name."""
    thread.title = title


def _frame(payload: dict) -> bytes:
    """One SSE data frame, as the chat stream spells them."""
    return f"data: {json.dumps(payload)}\n\n".encode()
