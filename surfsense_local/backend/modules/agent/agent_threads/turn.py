"""One turn of an agent thread, streamed in the chat's own frames.

opencode holds the turn; this sends the message, relays what the session does
until it is idle, then states the reply as opencode stored it. Closing the
stream stops the turn: nothing works on unseen.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import httpx
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.agent_threads.replies import turn_reply
from modules.agent.agent_threads.turn_frames import TurnFrames
from modules.agent.engine_choice import selected_model_can_run_agent
from modules.agent.opencode_client import OpencodeVersionError
from modules.agent.opencode_runtime import (
    AgentUnavailableError,
    ReadyAgent,
    ready_opencode,
)
from modules.agent.sources_folder import sync_sources_folder
from modules.chat.models import ChatThread
from modules.chat.schemas import MessageCreate
from modules.llm.resolution import ModelResolutionError

logger = logging.getLogger(__name__)

# A dropped or silent event stream is reopened; this many failures in a row
# means opencode is gone rather than restarting.
RECONNECTS = 20
_RECONNECT_SECONDS = 0.5
# As long as a chat title runs before it is cut, so a thread reads the same in the list.
TITLE_CHARS = 60
_DONE = b"data: [DONE]\n\n"


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
    try:
        ready = await ready_opencode(session, launch_key=launch_key)
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except (AgentUnavailableError, OpencodeVersionError) as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    # Checked once the model resolves, so a thread left with no model still asks for one.
    if not await selected_model_can_run_agent(session):
        await ready.client.close()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The selected model cannot run the agent. Choose another model, "
            "or start a new chat to use this one.",
        )
    folder = await transact(session, sync_sources_folder, thread.workspace_id)
    title = _first_title(thread, payload.text)
    if title is not None:
        await transact(session, _rename, thread, title)
    return StreamingResponse(
        _stream(ready, folder, session_id, payload.text, title),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream(
    ready: ReadyAgent, folder: Path, session_id: str, text: str, title: str | None
) -> AsyncIterator[bytes]:
    """The turn's frames, from the message sent to the reply stored."""
    client = ready.client
    turn = TurnFrames(session_id)
    sent = False
    try:
        failures = 0
        while not turn.finished:
            try:
                async for event in client.events(folder):
                    failures = 0
                    if event.type == "server.connected":
                        # Opened before sending, so not one of the turn's events is missed.
                        if not sent:
                            await client.send_turn(
                                folder, session_id, text, model=ready.model
                            )
                            sent = True
                        elif await client.status(folder, session_id) == "idle":
                            turn.finished = True  # it ended while the stream was down
                            break
                        continue
                    for frame in turn.frames(event):
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
            reply = turn_reply(
                await client.messages(folder, session_id), turn.user_message_id
            )
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
            await client.close()


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
