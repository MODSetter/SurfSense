import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from api.dependencies import SessionDep
from modules.chat.dependencies import ThreadDep
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
from modules.llm.models import ModelRole, SelectedModel
from modules.llm.providers import get_provider
from modules.workspaces.dependencies import WorkspaceDep
from shared.search import retrieve

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
    selected = session.get(SelectedModel, ModelRole.GENERATION)
    if selected is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no chat model selected")
    generator = get_provider(selected.provider, session)
    if generator is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"unknown provider: {selected.provider}"
        )
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
    should_generate_title = (
        not history and (thread.title or "").casefold() == "new chat"
    )
    hits = retrieve(
        session,
        thread.workspace_id,
        payload.text,
        document_ids=payload.document_ids,
    )
    context, citations = build_context(hits)
    messages = build_messages(context, history, payload.text)

    user_message = ChatMessage(
        chat_thread_id=thread.id,
        role=MessageRole.USER,
        content={"text": payload.text},
    )
    assistant_message = ChatMessage(
        chat_thread_id=thread.id,
        role=MessageRole.ASSISTANT,
        content={"text": "", "citations": []},
    )
    session.add_all((user_message, assistant_message))
    # Do not hold a write transaction open while the model generates. The IDs
    # are also the stable identities the client uses throughout the stream.
    session.commit()
    user_created_at = user_message.created_at.isoformat()

    async def stream() -> AsyncIterator[bytes]:
        parts: list[str] = []
        cited: list[dict] = []
        assistant_completed_at: str | None = None
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
                    thread.title = title
                    session.commit()
                    yield _frame({"type": "thread-title-update", "title": title})
            except Exception:
                session.rollback()
                logger.warning(
                    "Chat title generation failed for thread %s",
                    thread.id,
                    exc_info=True,
                )
        try:
            try:
                async for delta in generator.chat(selected.name, messages):
                    parts.append(delta)
                    yield _frame({"type": "delta", "text": delta})
            except Exception as exc:
                # Surfaced as an event; the partial turn is still stored below.
                yield _frame({"type": "error", "message": str(exc)})
        finally:
            # Keep source ids stable across the stream and stored answer. Invented
            # tokens are removed and never become clickable citations.
            answer, used = resolve_citations("".join(parts), citations)
            cited = [asdict(citation) for citation in used]
            assistant_message.content = {"text": answer, "citations": cited}
            assistant_message.completed_at = datetime.now(UTC)
            session.commit()
            session.refresh(assistant_message, attribute_names=["completed_at"])
            assistant_completed_at = assistant_message.completed_at.isoformat()

        if cited:
            yield _frame({"type": "citations", "items": cited})
        yield _frame(
            {
                "type": "completed",
                "assistant_completed_at": assistant_completed_at,
            }
        )
        yield _DONE

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # Keep a proxy from buffering or caching a live stream into one late blob.
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _frame(payload: dict) -> bytes:
    """One SSE data frame in the stream's accepted/delta/terminal protocol."""
    return f"data: {json.dumps(payload)}\n\n".encode()


_DONE = b"data: [DONE]\n\n"
