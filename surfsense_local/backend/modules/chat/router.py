import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.chat.dependencies import ThreadDep
from modules.chat.errors import classify_chat_error
from modules.chat.history import build_messages
from modules.chat.models import ChatMessage, ChatThread, MessageRole
from modules.chat.prompt import build_context, resolve_citations
from modules.chat.schemas import (
    MessageCreate,
    MessageRead,
    ThreadCreate,
    ThreadRead,
    ThreadUpdate,
)
from modules.chat.title import generate_title
from modules.documents.sources import load_selected_sources
from modules.llm.activity import ModelBusyError, model_activity, model_key
from modules.llm.resolution import (
    ModelResolutionError,
    ResolvedGeneration,
    resolve_generation,
)
from modules.workspaces.dependencies import WorkspaceDep
from shared.search import Hit, retrieve

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


@router.post(
    "/workspaces/{workspace_id}/chat/threads",
    response_model=ThreadRead,
    status_code=status.HTTP_201_CREATED,
    summary="Open a chat thread",
)
def create_thread(
    workspace: WorkspaceDep, payload: ThreadCreate, session: SessionDep
) -> ChatThread:
    thread = ChatThread(workspace_id=workspace.id, title=payload.title)
    session.add(thread)
    session.flush()  # The id and timestamps come from the database.
    return thread


@router.get(
    "/workspaces/{workspace_id}/chat/threads",
    response_model=list[ThreadRead],
    summary="List chat threads",
)
def list_threads(workspace: WorkspaceDep, session: SessionDep) -> Sequence[ChatThread]:
    return session.scalars(
        select(ChatThread)
        .where(ChatThread.workspace_id == workspace.id)
        .order_by(ChatThread.created_at.desc())
    ).all()


@router.patch(
    "/chat/threads/{thread_id}",
    response_model=ThreadRead,
    summary="Rename a chat thread",
)
def update_thread(thread: ThreadDep, payload: ThreadUpdate) -> ChatThread:
    thread.title = payload.title
    return thread


@router.get(
    "/chat/threads/{thread_id}/messages",
    response_model=list[MessageRead],
    summary="Read a thread's messages",
)
def list_messages(thread: ThreadDep, session: SessionDep) -> Sequence[ChatMessage]:
    return session.scalars(
        select(ChatMessage)
        .where(ChatMessage.chat_thread_id == thread.id)
        .order_by(ChatMessage.created_at)
    ).all()


@router.delete(
    "/chat/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a thread and its messages",
)
def delete_thread(thread: ThreadDep, session: SessionDep) -> Response:
    session.delete(thread)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/chat/threads/{thread_id}/messages",
    summary="Send a message and stream the grounded reply",
)
async def send_message(
    thread: ThreadDep, payload: MessageCreate, session: SessionDep
) -> StreamingResponse:
    resolved, history, hits = await transact(session, _ground, thread, payload)
    selected = resolved.selection
    generator = resolved.generator
    should_generate_title = (
        not history and (thread.title or "").casefold() == "new chat"
    )
    context, citations = build_context(hits, resolved.tier)
    logger.info(
        "chat: model %s/%s answering on the %s prompt (%s excerpts)",
        selected.provider,
        selected.name,
        resolved.tier,
        len(citations),
    )
    messages = build_messages(context, history, payload.text)

    activity_key = model_key(selected.provider, selected.name, selected.connection_id)
    try:
        await model_activity.acquire_use(activity_key)
    except ModelBusyError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    try:
        # The IDs are the stable identities the client uses throughout the stream.
        user_message, assistant_message = await transact(
            session, _open_turn, thread, payload.text
        )
        user_created_at = _iso(user_message.created_at)
    except Exception:
        await model_activity.release_use(activity_key)
        raise

    async def stream() -> AsyncIterator[bytes]:
        parts: list[str] = []
        failed = False
        title: str | None = None
        yield _frame(
            {
                "type": "accepted",
                "user_message_id": user_message.id,
                "assistant_message_id": assistant_message.id,
                "user_created_at": user_created_at,
            }
        )
        yield _frame(
            {
                "type": "citation-catalog",
                "items": [asdict(citation) for citation in citations],
            }
        )
        if should_generate_title:
            try:
                title = await generate_title(generator, selected.name, payload.text)
                if title:
                    # Shown optimistically; the rename only commits below if
                    # this turn ends up with a real reply, keeping a thread
                    # from staying renamed with nothing in it after a reload.
                    yield _frame({"type": "thread-title-update", "title": title})
            except Exception:
                session.rollback()
                logger.warning(
                    "Chat title generation failed for thread %s",
                    thread.id,
                    exc_info=True,
                )
        cited: list[dict] = []
        answer = ""
        assistant_completed_at: str | None = None
        try:
            try:
                async for delta in generator.chat(selected.name, messages):
                    parts.append(delta)
                    yield _frame({"type": "delta", "text": delta})
            except Exception as exc:
                # Surfaced as an event; a turn with no content at all is
                # discarded below rather than left as an empty, unexplained
                # reply. `finally` still runs on a client disconnect (that
                # raises outside Exception), so a partial reply is never lost.
                kind, message = classify_chat_error(exc, selected.provider)
                yield _frame(
                    {
                        "type": "error",
                        "kind": kind,
                        "message": message,
                        "provider": selected.provider,
                    }
                )
                failed = True
        finally:
            if failed and not parts:
                await transact(
                    session, _discard_turn, user_message, assistant_message
                )
            else:
                # A turn worth keeping: commit the deferred rename alongside
                # it, so a thread is never renamed unless it ends up with a
                # real first reply.
                if should_generate_title and title:
                    await transact(session, _rename, thread, title)
                # Rewrite [n] to [citation:<chunk_id>]. Invented tokens are dropped.
                answer, used = resolve_citations("".join(parts), citations)
                cited = [asdict(citation) for citation in used]
                await transact(session, _complete, assistant_message, answer, cited)
                assistant_completed_at = _iso(assistant_message.completed_at)

        if failed and not parts:
            yield _DONE
            return

        if cited:
            yield _frame({"type": "citations", "items": cited})
        yield _frame(
            {
                "type": "completed",
                "assistant_completed_at": assistant_completed_at,
                "text": answer,
            }
        )
        yield _DONE

    return StreamingResponse(
        _release_model_after(stream(), activity_key),
        media_type="text/event-stream",
        # Keep a proxy from buffering or caching a live stream into one late blob.
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _release_model_after(
    frames: AsyncIterator[bytes], key: tuple[str, ...]
) -> AsyncIterator[bytes]:
    try:
        async for frame in frames:
            yield frame
    finally:
        await model_activity.release_use(key)


# The stream's session work, each piece one short transaction off the event loop.


def _ground(
    session: Session, thread: ChatThread, payload: MessageCreate
) -> tuple[ResolvedGeneration, Sequence[ChatMessage], list[Hit]]:
    """The model to answer with, the turns so far, and the passages to cite."""
    try:
        resolved = resolve_generation(session)
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    if payload.document_ids is not None:
        load_selected_sources(session, thread.workspace_id, payload.document_ids)
    # Keep numpy/onnxruntime lazy: only chat and ingestion need this module.
    from worker.ingestion.embedding import missing_embedding_files

    if missing_embedding_files():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "local embedding model is not installed; "
            "run `uv run scripts/fetch_embedding_model.py`",
        )
    # History is the turns already stored; the new user turn is appended after.
    history = session.scalars(
        select(ChatMessage)
        .where(ChatMessage.chat_thread_id == thread.id)
        .order_by(ChatMessage.created_at)
    ).all()
    hits = retrieve(
        session, thread.workspace_id, payload.text, document_ids=payload.document_ids
    )
    return resolved, history, hits


def _open_turn(
    session: Session, thread: ChatThread, text: str
) -> tuple[ChatMessage, ChatMessage]:
    user_message = ChatMessage(
        chat_thread_id=thread.id, role=MessageRole.USER, content={"text": text}
    )
    assistant_message = ChatMessage(
        chat_thread_id=thread.id,
        role=MessageRole.ASSISTANT,
        content={"text": "", "citations": []},
    )
    session.add_all((user_message, assistant_message))
    session.flush()
    session.refresh(user_message)  # created_at is server-side; load it here
    return user_message, assistant_message


def _rename(_session: Session, thread: ChatThread, title: str) -> None:
    thread.title = title


def _discard_turn(
    session: Session, user_message: ChatMessage, assistant_message: ChatMessage
) -> None:
    """A turn that produced no content at all leaves no trace, not a blank reply."""
    session.delete(assistant_message)
    session.delete(user_message)


def _complete(
    _session: Session, message: ChatMessage, answer: str, cited: list[dict]
) -> None:
    message.content = {"text": answer, "citations": cited}
    message.completed_at = datetime.now(UTC)


def _iso(instant: datetime) -> str:
    """Spelled as Pydantic spells the REST timestamps: UTC as Z."""
    return instant.isoformat().replace("+00:00", "Z")


def _frame(payload: dict) -> bytes:
    """One SSE data frame in the stream's accepted/delta/terminal protocol."""
    return f"data: {json.dumps(payload)}\n\n".encode()


_DONE = b"data: [DONE]\n\n"
