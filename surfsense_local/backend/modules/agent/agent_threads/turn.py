"""One turn of an agent thread, run in the background in the chat's own frames.

opencode holds the turn; this sends the message, relays what the session does
until it is idle, then states the reply as opencode stored it. The turn is a
run: a window that hangs up stops following it, not the turn; Stop and quit
end it.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable
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
from modules.agent.plugin_tools.changed_tools import (
    check_after_turn,
    check_changed_tools,
)
from modules.agent.plugin_tools.give_plugins import (
    give_plugins,
    servers,
    set_plugin_rules,
)
from modules.agent.plugin_tools.mentions import (
    Mention,
    mention_note,
    mentioned_plugins,
)
from modules.agent.plugin_tools.refreshed_sign_ins import refresh_sign_ins
from modules.agent.plugin_tools.stop_plugin_calls import (
    HostCalls,
    stop_plugin_calls,
)
from modules.agent.plugin_tools.turn_plugins import TurnPlugin, turn_plugins
from modules.agent.plugin_tools.unavailable_plugin import UnavailablePlugin
from modules.agent.thread_folder.sync import ThreadGoneError, sync_thread_folder
from modules.agent.tool_endpoint.failed_renders import begin_turn
from modules.agent.tool_endpoint.registration import SERVER, register_thread_tools
from modules.chat.errors import classify_chat_error
from modules.chat.models import ChatThread
from modules.chat.runs.notify import notify_run
from modules.chat.runs.registry import ChatRuns
from modules.chat.runs.run import Run, RunState
from modules.chat.runs.stream import event_stream
from modules.chat.schemas import MessageCreate
from modules.events.broker import EventBroker
from modules.llm.resolution import ModelResolutionError
from modules.plugins.license_verdict.license_refresh import refresh_license_verdict
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
    # What another engine did in this thread while opencode was away.
    handover: str | None = None


@dataclass(frozen=True)
class _Tools:
    """What the turn's opencode was given: the plugins mentioned, the plugins, and those it cannot use."""

    mentions: list[Mention]
    plugins: list[TurnPlugin]
    unavailable: list[UnavailablePlugin]


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
    handover: str | None = None,
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
        title = first_title(thread, payload.text)
        if title is not None:
            await transact(session, _rename, thread, title)
    except BaseException:
        await ready.client.close()
        raise
    sending = _Sending(payload.text, sources, title, handover)
    thread_id, workspace_id = thread.id, thread.workspace_id

    async def frames(run: Run) -> AsyncIterator[bytes]:
        # The run outlives this request, so it keeps its own session.
        with place.session_factory() as run_session:
            async for frame in _stream(
                run,
                run_session,
                place.session_factory,
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
    sessions: sessionmaker[Session],
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
    host_calls = HostCalls()
    sent = False
    plugins: list[TurnPlugin] = []
    live_instances.turn_began(folder)
    try:
        # A big scope's first sync takes about 30 s: the thread says why it waits.
        count = len(sending.sources.document_ids)
        yield _frame({"type": "agent-preparing", "count": count})
        started = time.perf_counter()
        took: dict[str, float] = {}
        prepared: asyncio.Task[_Tools] | None = None
        try:
            if thread is None:
                raise ThreadGoneError(thread_id)
            # The turn's first call into its instance: one being disposed is finished first.
            await live_instances.wait_for_disposal(folder)
            # Given while the sources sync, so neither waits on the other's network or disk.
            prepared = asyncio.create_task(
                _prepare_tools(
                    sessions,
                    client,
                    folder,
                    where,
                    launch_key,
                    session_id,
                    sending.text,
                    took,
                )
            )
            # Commits its own short reads: files are written with the write lock free.
            await _timed(
                took,
                "sync",
                run_in_threadpool(
                    sync_thread_folder, session, thread, sending.sources.document_ids
                ),
            )
        except (ThreadGoneError, OSError) as error:
            _drop(prepared)
            logger.warning(
                "thread %s's sources were not prepared", thread_id, exc_info=True
            )
            yield _frame(_not_prepared(error))
            yield _DONE
            return
        except BaseException:
            _drop(prepared)
            raise
        tools = await prepared
        mentions, plugins, unavailable = (
            tools.mentions,
            tools.plugins,
            tools.unavailable,
        )
        _log_preparation(thread_id, started, took)
        if unavailable:
            yield _frame(
                {
                    "type": "agent-plugins-unavailable",
                    "plugins": [
                        {"title": p.title, "reason": p.reason} for p in unavailable
                    ],
                }
            )
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
                                notes=[
                                    note
                                    for note in (
                                        sending.handover,
                                        sending.sources.note,
                                        mention_note(mentions),
                                    )
                                    if note is not None
                                ],
                            )
                            sent = True
                        elif await client.status(folder, session_id) == "idle":
                            turn.finished = True  # it ended while the stream was down
                            break
                        continue
                    for frame in turn.frames(event):
                        follow_approvals(run, waiting, frame)
                        host_calls.follow(frame, plugins)
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
        # While the user reads the reply, so the next turn rarely waits on a check.
        check_after_turn(sessions)
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
                await stop_plugin_calls(plugins)
            else:
                host_calls.end()
            if sent and not turn.finished:
                try:
                    await client.abort(folder, session_id)
                except httpx.HTTPError:
                    logger.warning(
                        "could not stop agent turn in %s", session_id, exc_info=True
                    )
            await live_instances.turn_ended(client, folder)
            await client.close()


async def _prepare_tools(
    sessions: sessionmaker[Session],
    client: OpencodeClient,
    folder: Path,
    where: tuple[int, int],
    launch_key: str,
    session_id: str,
    text: str,
    took: dict[str, float],
) -> _Tools:
    """SurfSense's tools and the ready plugins given to the folder's opencode, and the session's rules set.

    In a session of its own, as it runs beside the sync. The plugins are given
    while their check runs; the rules wait for the check, so a tool it switched
    off is denied before the model is asked. A turn fails if opencode cannot say
    which servers it holds, or if their rules cannot be set.
    """
    workspace_id, thread_id = where
    with sessions() as session:
        signed_out = await _timed(took, "refresh", refresh_sign_ins(session))
        # Before the listings below: a plugin held out over its license is not listed.
        licensed_out = [
            UnavailablePlugin(title, "license")
            for title in await refresh_license_verdict(session, if_stale=True)
        ]
        mentions = await transact(session, mentioned_plugins, text)
        mentioned = frozenset(m.plugin_id for m in mentions)
        planned = await transact(session, turn_plugins, where, launch_key, mentioned)
        checked = asyncio.create_task(
            _timed(took, "check", check_changed_tools(sessions))
        )
        try:
            held = await client.tool_servers(folder)
        except httpx.HTTPError:
            # Fails closed: a server opencode holds keeps the last turn's rules,
            # which may allow a tool switched off since, and only a rule denying
            # every tool, opencode's own too, could deny a server not named.
            await checked
            raise
        registered = asyncio.create_task(
            _timed(
                took,
                "register",
                register_thread_tools(
                    client,
                    folder,
                    workspace_id,
                    thread_id,
                    launch_key,
                    held.get(SERVER),
                ),
            )
        )
        given = await _timed(took, "give", give_plugins(client, folder, held, planned))
        took["listed"] = await checked
        # Read as the check left them, not as rows the planned read still holds.
        session.expire_all()
        plugins = await transact(session, turn_plugins, where, launch_key, mentioned)
        added = given.added
        if servers(plugins) != servers(planned):
            # A server that failed already is not waited on twice.
            given = await give_plugins(client, folder, held, plugins, given.failed)
            added += given.added
        took["added"] = added
        try:
            await _timed(
                took,
                "rules",
                set_plugin_rules(client, folder, session_id, held, plugins),
            )
        except httpx.HTTPError:
            if plugins or held.keys() - {SERVER}:
                # Fails closed: the last turn's rules would allow a server given
                # since, and a tool switched off since.
                _drop(registered)
                raise
            logger.warning("%s's plugin rules were not set", folder, exc_info=True)
        took["registered"] = await registered
    return _Tools(mentions, plugins, signed_out + licensed_out + given.unavailable)


async def _timed[T](took: dict[str, float], stage: str, work: Awaitable[T]) -> T:
    """Await `work`, noting in `took` how many milliseconds it took."""
    began = time.perf_counter()
    try:
        return await work
    finally:
        took[stage] = (time.perf_counter() - began) * 1000


def _log_preparation(thread_id: int, started: float, took: dict[str, float]) -> None:
    """One line per turn: where the wait before the model was asked went, in ms.

    The sync runs beside the rest, so the stages add up to more than the whole.
    """
    logger.info(
        "thread %s prepared in %.0f ms: sync %.0f, refresh %.0f, check %.0f "
        "(%d listed), give %.0f (%d added), rules %.0f, register %.0f (%s)",
        thread_id,
        (time.perf_counter() - started) * 1000,
        took.get("sync", 0),
        took.get("refresh", 0),
        took.get("check", 0),
        took.get("listed", 0),
        took.get("give", 0),
        took.get("added", 0),
        took.get("rules", 0),
        took.get("register", 0),
        "given" if took.get("registered") else "held",
    )


def _drop(task: asyncio.Task | None) -> None:
    """Cancel a task the turn no longer waits on; any failure it had is only logged."""
    if task is None:
        return
    task.cancel()
    task.add_done_callback(
        lambda done: (
            done.cancelled()
            or done.exception() is None
            or logger.warning(
                "a turn's tools were not given", exc_info=done.exception()
            )
        )
    )


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


def follow_approvals(run: Run, waiting: set[str], frame: dict) -> None:
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


def first_title(thread: ChatThread, text: str) -> str | None:
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
