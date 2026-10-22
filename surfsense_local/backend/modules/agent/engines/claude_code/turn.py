"""One turn of an agent thread on Claude Code, run in the background in the chat's own frames.

The turn is prepared as opencode's is (the folder synced, the plugins checked),
then the thread's Claude Code runs it. Its messages, and the approvals its
calls wait on, are read as opencode's events, so the thread shows the same
frames whichever engine answers (docs/architecture/claude-plan.md).
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anyio
from claude_agent_sdk import SystemMessage
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.agent_threads.citations import load_citations, searched_chunks
from modules.agent.agent_threads.ready_renders import link_live_render
from modules.agent.agent_threads.replies import reply_id, turn_reply
from modules.agent.agent_threads.turn import (
    RunPlace,
    first_title,
    follow_approvals,
)
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.agent_threads.turn_sources import turn_sources
from modules.agent.engines.claude_code.agent_options import AgentLaunch, agent_options
from modules.agent.engines.claude_code.agent_runs import AgentRuns, HeldRun
from modules.agent.engines.claude_code.approvals import APPROVALS
from modules.agent.engines.claude_code.endings import (
    INTERRUPTED,
    STOPPED,
    finished,
    record_ending,
)
from modules.agent.engines.claude_code.gate import Gate
from modules.agent.engines.claude_code.mcp_config import write_mcp_config
from modules.agent.engines.claude_code.models import ClaudeSessionEntry
from modules.agent.engines.claude_code.opencode_shape import OpencodeShape
from modules.agent.engines.claude_code.plugin_statuses import unavailable_plugins
from modules.agent.engines.claude_code.saved_results import claude_home
from modules.agent.engines.claude_code.session_files import drop_transcript
from modules.agent.engines.claude_code.session_store import ThreadSessionStore
from modules.agent.engines.claude_code.skills_plugin import SkillsPlugin
from modules.agent.engines.claude_code.tool_names import claude_tool, for_claude
from modules.agent.engines.claude_code.turn_link import TurnLink
from modules.agent.opencode_client import Event
from modules.agent.plugin_tools.changed_tools import (
    check_after_turn,
    check_changed_tools,
)
from modules.agent.plugin_tools.mentions import mention_note, mentioned_plugins
from modules.agent.plugin_tools.refreshed_sign_ins import refresh_sign_ins
from modules.agent.plugin_tools.stop_plugin_calls import stop_plugin_calls
from modules.agent.plugin_tools.turn_plugins import TurnPlugin, turn_plugins
from modules.agent.plugin_tools.unavailable_plugin import UnavailablePlugin
from modules.agent.thread_folder.sync import ThreadGoneError, sync_thread_folder
from modules.agent.tool_endpoint.failed_renders import begin_turn
from modules.agent.tool_endpoint.registration import SERVER, thread_tools_url
from modules.chat.errors import classify_chat_error
from modules.chat.models import ChatThread
from modules.chat.runs.notify import notify_run
from modules.chat.runs.run import Run
from modules.chat.runs.stream import event_stream
from modules.chat.schemas import MessageCreate
from modules.egress.service import EgressDeniedError
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.subscriptions.claude.account import CLAUDE_PLAN
from modules.llm.subscriptions.claude.errors import (
    ClaudeSignInRequiredError,
    failure_of,
)
from modules.llm.subscriptions.claude.extra_usage import plan_usage
from modules.llm.subscriptions.claude.hosts import claude_refusal, require_claude_hosts
from modules.llm.subscriptions.claude.proxy import required_claude_proxy_url
from modules.llm.subscriptions.claude.run import ClaudeRun, open_run
from modules.llm.subscriptions.claude.usable_claude import usable_claude
from modules.llm.subscriptions.plan_usage_frame import plan_usage_frame
from modules.plugins.installed.models import PluginTool
from modules.plugins.license_verdict.license_refresh import refresh_license_verdict
from shared.config import get_storage_settings

logger = logging.getLogger(__name__)

PROVIDER = "claude_plan"
_DONE = b"data: [DONE]\n\n"
_END = object()
# Measured: interrupt() returned in 0.01 s and the turn's result came straight after.
END_SECONDS = 10.0


@dataclass(frozen=True)
class ClaudeSetup:
    """What every Claude Code turn shares: the running clients and SurfSense's skills."""

    runs: AgentRuns
    skills: SkillsPlugin
    # Where the MCP config files go, readable by the user alone.
    config_dir: Path


@dataclass(frozen=True)
class _Sending:
    text: str
    note: str | None
    shown: dict[str, Any] | None
    document_ids: list[int]
    title: str | None
    model: str
    thinking: bool
    # What opencode did in this thread while Claude Code was away.
    handover: str | None = None


@dataclass
class _Tools:
    plugins: list[TurnPlugin] = field(default_factory=list)
    unavailable: list[UnavailablePlugin] = field(default_factory=list)
    mentions: list[Any] = field(default_factory=list)
    hidden: list[str] = field(default_factory=list)
    # A digest of each plugin's offered tools, as SurfSense last listed them.
    listings: dict[str, str] = field(default_factory=dict)


async def claude_turn(
    session: Session,
    thread: ChatThread,
    payload: MessageCreate,
    launch_key: str,
    place: RunPlace,
    setup: ClaudeSetup,
    handover: str | None = None,
) -> StreamingResponse:
    """Start the turn as a run and follow it, or refuse before anything is sent."""
    if thread.claude_session_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "this thread is not the agent's")
    if payload.images:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The agent does not read attached images yet. Send the text alone.",
        )
    model = await transact(session, _claude_model)
    if model is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The selected model is not a Claude plan model. Choose one, or start a "
            "new chat to use this one.",
        )
    # Before anything runs, so the window asks for the hosts as it does for a chat.
    await transact(session, require_claude_hosts)
    # Found once, here, so an old Claude Code is refused before the turn starts.
    binary = await run_in_threadpool(usable_claude)
    sources = await transact(session, turn_sources, thread, payload)
    title = first_title(thread, payload.text)
    if title is not None:
        await transact(session, _rename, thread, title)
    sending = _Sending(
        payload.text,
        sources.note,
        sources.shown,
        list(sources.document_ids),
        title,
        model,
        payload.thinking,
        handover,
    )
    thread_id, workspace_id = thread.id, thread.workspace_id
    session_id = thread.claude_session_id

    async def frames(run: Run) -> AsyncIterator[bytes]:
        with place.session_factory() as run_session:
            async for frame in _stream(
                run,
                run_session,
                place.session_factory,
                (workspace_id, thread_id),
                session_id,
                launch_key,
                sending,
                setup,
                binary,
            ):
                yield frame

    async def ended() -> None:
        notify_run(place.broker, workspace_id, thread_id, "done")

    def moved(state: Any) -> None:
        notify_run(place.broker, workspace_id, thread_id, state.state)

    run = place.runs.start(thread_id, frames, on_end=ended, on_state=moved)
    notify_run(place.broker, workspace_id, thread_id, "running")
    return event_stream(run.follow())


async def _stream(
    run: Run,
    session: Session,
    sessions: sessionmaker[Session],
    where: tuple[int, int],
    session_id: str,
    launch_key: str,
    sending: _Sending,
    setup: ClaudeSetup,
    binary: Path,
) -> AsyncIterator[bytes]:
    """The turn's frames, from its sources prepared to the reply stated."""
    workspace_id, thread_id = where
    folder = get_storage_settings().thread_working_dir(workspace_id, thread_id)
    user_id = str(uuid.uuid4())
    reply = reply_id(user_id)
    frames = TurnFrames(session_id)
    shape = OpencodeShape(session_id)
    waiting: set[str] = set()
    tools = _Tools()
    held: HeldRun | None = None
    pump: asyncio.Task | None = None
    # Said once per reply, and again only if it changes.
    plan_said = None
    try:
        yield _frame({"type": "agent-preparing", "count": len(sending.document_ids)})
        thread = await transact(session, _reload, thread_id)
        try:
            if thread is None:
                raise ThreadGoneError(thread_id)
            prepared = asyncio.create_task(
                _prepare_tools(sessions, where, launch_key, sending.text)
            )
            await run_in_threadpool(
                sync_thread_folder, session, thread, sending.document_ids
            )
            tools = await prepared
        except (ThreadGoneError, OSError) as error:
            logger.warning(
                "thread %s's sources were not prepared", thread_id, exc_info=True
            )
            yield _frame(_not_prepared(error))
            yield _DONE
            return
        servers = _servers(workspace_id, thread_id, launch_key, tools.plugins)
        gate = Gate(
            folder=folder,
            skills=setup.skills.skills,
            skill_names=setup.skills.names,
            plugin_rules={
                claude_tool(plugin.name, tool): rule
                for plugin in tools.plugins
                for tool, rule in plugin.tools.items()
            },
            claude_home=claude_home(),
            session_id=session_id,
        )
        digest = _digest(sending, servers, tools.hidden, setup.skills)
        proxy_url = required_claude_proxy_url()
        store = ThreadSessionStore(sessions, thread_id)
        resumed = await transact(session, _has_session, session_id)

        async def start(link: TurnLink) -> tuple[ClaudeRun, Path]:
            mcp_file = write_mcp_config(setup.config_dir, servers)
            try:
                options = agent_options(
                    AgentLaunch(
                        binary=binary,
                        proxy_url=proxy_url,
                        folder=folder,
                        model=sending.model,
                        session_id=session_id,
                        resumed=resumed,
                        mcp_file=mcp_file,
                        disallowed=tools.hidden,
                        skills=setup.skills,
                        link=link,
                        store=store,
                        thinking=sending.thinking,
                    )
                )
                return await open_run(options), mcp_file
            except BaseException:
                mcp_file.unlink(missing_ok=True)
                raise

        held = await setup.runs.acquire(thread_id, digest, start, tools.listings)
        begin_turn(thread_id)
        if sending.shown is not None:
            yield _frame({"type": "agent-scope", "scope": sending.shown})
        await transact(session, record_ending, thread_id, reply, INTERRUPTED)

        events: asyncio.Queue[Any] = asyncio.Queue()
        held.link.begin(gate, events, session_id)
        pump = asyncio.create_task(
            _pump(held.run, _blocks(sending, tools.mentions), user_id, events)
        )
        for event in shape.user(user_id, int(time.time() * 1000)):
            for frame in frames.frames(event):
                yield _frame(frame)
                if frame["type"] == "accepted" and sending.title is not None:
                    yield _frame(
                        {"type": "thread-title-update", "title": sending.title}
                    )

        while (item := await events.get()) is not _END:
            if isinstance(item, BaseException):
                raise item
            if isinstance(item, Event):
                read = [item]
            elif isinstance(item, SystemMessage) and item.subtype == "init":
                # Sent once Claude Code's plugins have connected or failed: settled
                # here, as opencode's are once their add returns, and not before.
                unavailable = tools.unavailable + unavailable_plugins(
                    item.data.get("mcp_servers") or [], tools.plugins
                )
                if unavailable:
                    yield _frame(_unavailable_frame(unavailable))
                continue
            elif (usage := plan_usage(item)) is not None:
                if usage != plan_said:
                    plan_said = usage
                    yield _frame(plan_usage_frame(usage))
                continue
            else:
                refusal = (
                    await transact(session, claude_refusal)
                    if isinstance(item, SystemMessage) and item.subtype == "api_retry"
                    else None
                )
                if (failure := failure_of(item, proxy_refusal=refusal)) is not None:
                    raise failure
                read = shape.read(item)
            for event in read:
                for frame in frames.frames(event):
                    follow_approvals(run, waiting, frame)
                    if frame.get("artifact") is not None:
                        await transact(session, link_live_render, workspace_id, frame)
                    yield _frame(frame)

        messages = shape.messages()
        citations = await transact(
            session, load_citations, workspace_id, searched_chunks(messages)
        )
        stated = turn_reply(messages, user_id, citations)
        await transact(session, finished, thread_id, reply)
        if stated and stated["content"]["citations"]:
            yield _frame({"type": "citations", "items": stated["content"]["citations"]})
        yield _frame(
            {
                "type": "completed",
                "assistant_completed_at": stated["completed_at"] if stated else None,
                "text": stated["content"]["text"] if stated else "",
            }
        )
        yield _DONE
        check_after_turn(sessions)
    # The headers are sent: only a frame can tell the chat the turn ended.
    except Exception as failure:
        if not isinstance(failure, EgressDeniedError | ClaudeSignInRequiredError):
            logger.exception("Claude Code turn in thread %s failed", thread_id)
        kind, message = classify_chat_error(failure, PROVIDER)
        ending = {"type": "error", "kind": kind, "message": message}
        await transact(session, record_ending, thread_id, reply, ending)
        yield _frame(
            {"type": "error", "kind": kind, "message": message, "provider": PROVIDER}
        )
        yield _DONE
    finally:
        # Stop and quit cancel the run: the turn stops with it.
        with anyio.CancelScope(shield=True):
            stopped = run.stop_requested and not frames.finished
            if stopped:
                APPROVALS.drop(thread_id)
            if pump is not None and not pump.done():
                await _finish_reading(held, pump, setup.runs, thread_id)
            if stopped:
                await transact(session, record_ending, thread_id, reply, STOPPED)
                await stop_plugin_calls(tools.plugins)
            setup.runs.release(thread_id)
            await run_in_threadpool(drop_transcript, session_id)


async def _pump(
    run: ClaudeRun,
    blocks: list[dict[str, Any]],
    user_id: str,
    events: asyncio.Queue[Any],
) -> None:
    """Claude Code's messages into the turn's queue, beside the approvals its calls wait on."""
    try:
        async for message in run.send(blocks, uuid=user_id):
            await events.put(message)
    except Exception as error:
        await events.put(error)
    finally:
        await events.put(_END)


async def _prepare_tools(
    sessions: sessionmaker[Session],
    where: tuple[int, int],
    launch_key: str,
    text: str,
) -> _Tools:
    """The ready plugins and their rules, as opencode's turn plans them, read once the check ends."""
    with sessions() as session:
        signed_out = await refresh_sign_ins(session)
        licensed_out = [
            UnavailablePlugin(title, "license")
            for title in await refresh_license_verdict(session, if_stale=True)
        ]
        mentions = await transact(session, mentioned_plugins, text)
        await check_changed_tools(sessions)
        session.expire_all()
        plugins = await transact(session, turn_plugins, where, launch_key)
        hidden = await transact(session, _hidden_tools, plugins)
        listings = await transact(session, _listings, plugins)
    return _Tools(plugins, signed_out + licensed_out, mentions, hidden, listings)


def _hidden_tools(session: Session, plugins: list[TurnPlugin]) -> list[str]:
    """Each given plugin's tools with no rule: switched off or unreviewed."""
    hidden = []
    for plugin in plugins:
        for tool in session.scalars(
            select(PluginTool.tool).where(PluginTool.plugin_id == plugin.name)
        ):
            if tool not in plugin.tools:
                hidden.append(claude_tool(plugin.name, tool))
    return sorted(hidden)


def _listings(session: Session, plugins: list[TurnPlugin]) -> dict[str, str]:
    """What the model is told of each plugin's offered tools; a change needs the plugin connected again."""
    listings = {}
    for plugin in plugins:
        tools = session.scalars(
            select(PluginTool)
            .where(PluginTool.plugin_id == plugin.name)
            .where(PluginTool.tool.in_(plugin.tools))
            .order_by(PluginTool.tool)
        )
        told = [
            [tool.tool, tool.title, tool.description, tool.input_schema]
            for tool in tools
        ]
        listings[plugin.name] = hashlib.sha256(
            json.dumps(told, sort_keys=True).encode()
        ).hexdigest()
    return listings


def _servers(
    workspace_id: int, thread_id: int, launch_key: str, plugins: list[TurnPlugin]
) -> dict[str, Any]:
    servers: dict[str, Any] = {
        SERVER: {
            "type": "http",
            "url": thread_tools_url(workspace_id, thread_id),
            "headers": {"Authorization": f"Bearer {launch_key}"},
            # SurfSense's own tools are seen every turn, never behind a search.
            "alwaysLoad": True,
        }
    }
    for plugin in plugins:
        servers[plugin.name] = {
            "type": "http",
            "url": plugin.url,
            "headers": plugin.headers,
        }
    return servers


def _blocks(sending: _Sending, mentions: list[Any]) -> list[dict[str, Any]]:
    """SurfSense's notes first, each a block of its own, then the user's words."""
    notes = [
        note
        for note in (sending.handover, sending.note, mention_note(mentions))
        if note is not None
    ]
    return [
        *({"type": "text", "text": for_claude(note)} for note in notes),
        {"type": "text", "text": sending.text},
    ]


def _digest(
    sending: _Sending,
    servers: dict[str, Any],
    hidden: list[str],
    skills: SkillsPlugin,
) -> str:
    """What a running Claude Code was started with; another turn set up alike reuses it."""
    given = {
        "model": sending.model,
        "thinking": sending.thinking,
        "servers": servers,
        "hidden": hidden,
        "skills": sorted(skills.names),
    }
    return hashlib.sha256(json.dumps(given, sort_keys=True).encode()).hexdigest()


def _unavailable_frame(unavailable: list[UnavailablePlugin]) -> dict[str, Any]:
    return {
        "type": "agent-plugins-unavailable",
        "plugins": [{"title": p.title, "reason": p.reason} for p in unavailable],
    }


async def _finish_reading(
    held: HeldRun | None, pump: asyncio.Task, runs: AgentRuns, thread_id: int
) -> None:
    """Read the interrupted turn to its end, so its result is never the next turn's.

    Claude Code ends a turn it was interrupted in with a result of its own; one
    left unread would answer the next message. A turn that will not end is let go.
    """
    if held is not None:
        await _interrupt(held.run)
    try:
        await asyncio.wait_for(asyncio.shield(pump), END_SECONDS)
    except TimeoutError:
        pump.cancel()
        await runs.forget(thread_id)


async def _interrupt(run: ClaudeRun) -> None:
    try:
        await run.interrupt()
    except Exception:
        logger.warning("could not stop a Claude Code turn", exc_info=True)


def _claude_model(session: Session) -> str | None:
    """The selected text model's name, when a Claude plan serves it."""
    selected = session.get(SelectedModel, ModelType.TEXT_GEN)
    if selected is None or selected.connection is None:
        return None
    if selected.connection.auth_kind != CLAUDE_PLAN:
        return None
    return selected.name


def _has_session(session: Session, session_id: str) -> bool:
    """Whether Claude Code has run this session before, so it resumes rather than starts it."""
    return (
        session.scalar(
            select(ClaudeSessionEntry.id)
            .where(ClaudeSessionEntry.session_id == session_id)
            .limit(1)
        )
        is not None
    )


def _not_prepared(error: Exception) -> dict:
    message = (
        "This chat was deleted."
        if isinstance(error, ThreadGoneError)
        else f"The chat's sources could not be prepared: {error}"
    )
    return {
        "type": "error",
        "kind": "unknown",
        "message": message,
        "provider": PROVIDER,
    }


def _reload(session: Session, thread_id: int) -> ChatThread | None:
    return session.get(ChatThread, thread_id)


def _rename(_session: Session, thread: ChatThread, title: str) -> None:
    thread.title = title


def _frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()
