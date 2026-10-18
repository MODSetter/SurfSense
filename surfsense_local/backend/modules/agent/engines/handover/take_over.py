"""The session a thread's next turn runs in, and the note of what that session missed.

docs/architecture/claude-plan.md, Switching engines. Each engine keeps its own session and
resumes it; the note covers only the turns since it last answered, and goes
beside the user's message, so its session keeps it as it keeps the scope note.
A session the engine renewed missed the whole thread.
"""

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.engines.agent_engine import AgentEngine
from modules.agent.engines.both_sessions import thread_turns_of
from modules.agent.engines.handover.note import handover_note
from modules.agent.engines.thread_engine import every_engine, thread_engine
from modules.agent.thread_folder.layout import OUTPUTS
from modules.chat.models import ChatThread
from shared.config import get_storage_settings

# About 6,000 tokens: room for the turn in the smallest window the agent runs in, 32,768.
NOTE_CHARS = 24_000


async def take_over(
    session: Session, thread: ChatThread, taking: AgentEngine, launch_key: str
) -> str | None:
    """Run the thread's next turn on `taking`; the note for that turn, or None with nothing missed."""
    leaving = thread_engine(thread)
    moving = leaving is not taking
    seen = await _turns(session, thread, taking, launch_key) if moving else []
    await taking.ensure_session(session, thread, launch_key)
    if await taking.renew_session(session, thread):
        missed = await thread_turns_of(
            session, thread, launch_key, False, every_engine()
        )
    elif moving:
        missed = await _turns(session, thread, leaving, launch_key)
        since = _last_asked(seen)
        if since is not None:
            missed = _after(missed, since)
    else:
        return None
    if moving:
        await transact(session, _move, thread, taking)
    if not missed:
        return None
    folder = get_storage_settings().thread_working_dir(thread.workspace_id, thread.id)
    outputs = await run_in_threadpool(_outputs, folder)
    return handover_note(missed, outputs, NOTE_CHARS)


async def _turns(
    session: Session, thread: ChatThread, engine: AgentEngine, launch_key: str
) -> list[dict]:
    """The engine's own turns; none when it never ran the thread or cannot be read now."""
    if not engine.has_session(thread):
        return []
    try:
        return await engine.thread_messages(session, thread, launch_key, False)
    except HTTPException:
        return []


def _last_asked(turns: list[dict]) -> str | None:
    asked = [t["created_at"] for t in turns if t["role"] == "user" and t["created_at"]]
    return max(asked) if asked else None


def _after(turns: list[dict], since: str) -> list[dict]:
    """The turns opened after `since`, each with its reply."""
    kept: list[dict] = []
    keeping = False
    for turn in turns:
        if turn["role"] == "user":
            keeping = (turn["created_at"] or "") > since
        if keeping:
            kept.append(turn)
    return kept


def _outputs(folder: Path) -> list[str]:
    outputs = folder / OUTPUTS
    if not outputs.is_dir():
        return []
    return sorted(
        str(path.relative_to(folder).as_posix())
        for path in outputs.rglob("*")
        if path.is_file()
    )


def _move(session: Session, thread: ChatThread, taking: AgentEngine) -> None:
    thread.agent_engine = taking.kind
    session.flush()
    session.refresh(thread)
