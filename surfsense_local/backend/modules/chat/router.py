import base64
import binascii
import json
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict
from datetime import UTC, datetime

import anyio
from fastapi import APIRouter, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import SessionDep, transact
from modules.agent.agent_threads.forget_sessions import forget_thread
from modules.agent.agent_threads.open_session import open_agent_session
from modules.agent.agent_threads.thread_messages import agent_thread_messages
from modules.agent.agent_threads.turn import agent_turn
from modules.agent.dependencies import LaunchKeyDep
from modules.agent.engine_choice import selected_model_can_run_agent
from modules.agent.thread_folder.layout import remove_thread_folder
from modules.chat.budget import (
    IMAGE_TOKENS,
    answer_max_tokens,
    history_budget,
    image_room,
)
from modules.chat.dependencies import ThreadDep
from modules.chat.errors import classify_chat_error, empty_reply_error
from modules.chat.history import TokenCounter, build_messages
from modules.chat.images import store
from modules.chat.images.intake import ImageRefusedError, NormalisedImage, normalise
from modules.chat.images.sources import (
    MAX_SOURCE_IMAGES,
    image_source_paths,
    load_source_images,
)
from modules.chat.models import ChatMessage, ChatThread, MessageRole
from modules.chat.prompt import build_context, resolve_citations
from modules.chat.reasoning import ReasoningTrace
from modules.chat.schemas import (
    ImageUpload,
    MessageCreate,
    MessageRead,
    ThreadCreate,
    ThreadRead,
    ThreadUpdate,
)
from modules.chat.title import generate_title
from modules.documents.sources import load_selected_sources
from modules.embedding.active import require_active_index
from modules.llm.activity import ModelBusyError, model_activity, model_key
from modules.llm.providers.protocols import Generator
from modules.llm.resolution import (
    ModelResolutionError,
    ResolvedGeneration,
    resolve_generation,
)
from modules.source_scope.resolve import resolve_scope
from modules.source_scope.schemas import SourceScope
from modules.source_scope.thread_scope import store_thread_scope, thread_scope
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
async def create_thread(
    workspace: WorkspaceDep,
    payload: ThreadCreate,
    session: SessionDep,
    launch_key: LaunchKeyDep,
) -> ChatThread:
    """Open a thread, and give it to the agent when the selected model may run it.

    Chosen here and kept: the thread's turns live with whichever engine got it.
    """
    thread = await transact(
        session, _new_thread, workspace.id, payload.title, payload.source_scope
    )
    if await selected_model_can_run_agent(session):
        session_id = await open_agent_session(session, thread, launch_key)
        if session_id is not None:
            await transact(session, _give_to_agent, thread, session_id)
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
async def list_messages(
    thread: ThreadDep, session: SessionDep, launch_key: LaunchKeyDep
) -> Sequence[ChatMessage] | list[dict]:
    if thread.uses_agent:
        return await agent_thread_messages(session, thread, launch_key)
    return await transact(session, _stored_turns, thread)


@router.delete(
    "/chat/threads/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a thread and its messages",
)
async def delete_thread(thread: ThreadDep, session: SessionDep) -> Response:
    workspace_id, thread_id = thread.workspace_id, thread.id
    folder = None
    if thread.opencode_session_id is not None:
        folder = await forget_thread(
            workspace_id, thread_id, thread.opencode_session_id
        )
    await transact(session, _delete_thread, thread)
    store.remove_thread(workspace_id, thread_id)
    if folder is not None:
        # Unlinks the views; their cached texts stay for the threads still using them.
        await run_in_threadpool(remove_thread_folder, folder)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _delete_thread(session: Session, thread: ChatThread) -> None:
    """Delete the row; its messages cascade and its artifacts are kept.

    `transact` commits before the caller removes the files, which a rollback
    would otherwise leave pointing at nothing.
    """
    session.delete(thread)


@router.get(
    "/chat/threads/{thread_id}/messages/{message_id}/images/{index}",
    response_class=FileResponse,
    summary="Read an image a turn carried",
)
def read_message_image(
    thread: ThreadDep, message_id: int, index: int, session: SessionDep
) -> FileResponse:
    message = session.get(ChatMessage, message_id)
    references = (
        message.content.get("images", [])
        if message is not None and message.chat_thread_id == thread.id
        else []
    )
    if not 0 <= index < len(references):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such image")
    path = store.image_path(references[index])
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "the image is no longer on disk")
    # Only PNG and JPEG are ever stored, so inline cannot run a script.
    return FileResponse(path, media_type=references[index]["mime"])


@router.post(
    "/chat/threads/{thread_id}/messages",
    summary="Send a message and stream the grounded reply",
)
async def send_message(
    thread: ThreadDep,
    payload: MessageCreate,
    session: SessionDep,
    launch_key: LaunchKeyDep,
) -> StreamingResponse:
    if thread.uses_agent:
        return await agent_turn(session, thread, payload, launch_key)
    resolved, history, hits, scope_record = await transact(
        session, _ground, thread, payload
    )
    selected = resolved.selection
    generator = resolved.generator
    # Asked once: it gates attachments and decides whether sources send pictures.
    sees = await generator.sees_images(selected.name)
    images = await _accepted_images(payload.images, sees)
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
    n_ctx = await _context_tokens_or_none(generator, selected.name)
    _refuse_images_past_window(len(images), n_ctx, len(context) + len(payload.text))
    found = await _source_images(session, hits, sees, n_ctx, len(images))
    messages = await build_messages(
        context,
        history,
        payload.text,
        images=[image.as_part() for image in (*images, *found)],
        history_budget=history_budget(n_ctx),
        token_count=_token_counter(generator, selected.name),
    )

    activity_key = model_key(selected.provider, selected.name, selected.connection_id)
    try:
        await model_activity.acquire_use(activity_key)
    except ModelBusyError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    try:
        # The IDs are the stable identities the client uses throughout the stream.
        user_message, assistant_message = await transact(
            session, _open_turn, thread, payload.text, images, scope_record
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
        trace = ReasoningTrace()
        try:
            try:
                async for delta in generator.chat_deltas(
                    selected.name,
                    messages,
                    max_tokens=answer_max_tokens(n_ctx),
                    # None leaves the model to its own default.
                    reasoning=None if payload.thinking else False,
                ):
                    if delta.progress is not None:
                        yield _frame(
                            {
                                "type": "prompt-progress",
                                "processed": delta.progress.processed,
                                "total": delta.progress.total,
                            }
                        )
                        continue
                    if delta.reasoning:
                        trace.add(delta.text)
                        yield _frame({"type": "reasoning", "text": delta.text})
                        continue
                    if (duration_ms := trace.end()) is not None:
                        yield _frame(
                            {"type": "reasoning-end", "duration_ms": duration_ms}
                        )
                    parts.append(delta.text)
                    yield _frame({"type": "delta", "text": delta.text})
                # A think that used the whole budget never reaches an answer.
                if (duration_ms := trace.end()) is not None:
                    yield _frame({"type": "reasoning-end", "duration_ms": duration_ms})
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
            # Starlette cancels the response task on disconnect. The turn still
            # has to settle before the request scope disappears.
            with anyio.CancelScope(shield=True):
                # No answer text is no reply, whether it failed, closed cleanly
                # or only thought: keeping it would leave a blank bubble and a
                # rename.
                if not parts:
                    await transact(
                        session, _discard_turn, user_message, assistant_message
                    )
                    if images:
                        await transact(session, _sweep_images, thread)
                else:
                    # A turn worth keeping: commit the deferred rename alongside
                    # it, so a thread is never renamed unless it ends up with a
                    # real first reply.
                    if should_generate_title and title:
                        await transact(session, _rename, thread, title)
                    # Rewrite [n] to [citation:<chunk_id>]. Invented tokens are dropped.
                    answer, used = resolve_citations("".join(parts), citations)
                    cited = [asdict(citation) for citation in used]
                    await transact(
                        session,
                        _complete,
                        assistant_message,
                        answer,
                        cited,
                        trace.stored(),
                    )
                    assistant_completed_at = _iso(assistant_message.completed_at)

        if not parts:
            if not failed:
                # Discarding the turn removes the person's own message too, so
                # say so rather than close in silence.
                kind, message = empty_reply_error()
                yield _frame(
                    {
                        "type": "error",
                        "kind": kind,
                        "message": message,
                        "provider": selected.provider,
                    }
                )
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
        with anyio.CancelScope(shield=True):
            await model_activity.release_use(key)


async def _accepted_images(
    uploads: list[ImageUpload], sees: bool | None
) -> list[NormalisedImage]:
    """The turn's images, normalised, or the refusal that stores nothing.

    Only a definite no refuses: an unreadable runtime lets the turn through,
    and llama-server's own error stops an image it cannot take.
    """
    if not uploads:
        return []
    if sees is False:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This model can't read images. Choose one that can, or send the text alone.",
        )
    try:
        return await run_in_threadpool(_normalised, uploads)
    except ImageRefusedError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
        ) from error


def _refuse_images_past_window(
    attached: int, n_ctx: int | None, text_chars: int
) -> None:
    """Refuse before anything is stored a turn whose images overflow even at
    Gemma 3's 256 each: trimming history cannot make room for them, so the model would only
    fail it later as `context_too_long`."""
    room = image_room(n_ctx, text_chars)
    if room is None or attached <= room:
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        (
            "This model's context window has no room for images."
            if room == 0
            else f"This model's context window has room for at most {room} "
            + ("image." if room == 1 else "images.")
        )
        + " Send fewer, or choose a model with a larger window.",
    )


async def _source_images(
    session: Session,
    hits: list[Hit],
    sees: bool | None,
    n_ctx: int | None,
    attached: int,
) -> list[NormalisedImage]:
    """Retrieved image sources, only for a model known to see, and only as many
    as the window has room for once the person's own images are paid for."""
    room = (history_budget(n_ctx) - IMAGE_TOKENS * attached) // IMAGE_TOKENS
    limit = min(MAX_SOURCE_IMAGES, room)
    if sees is not True or limit <= 0 or not hits:
        return []
    paths = await transact(session, image_source_paths, hits, limit)
    return await run_in_threadpool(load_source_images, paths)


def _normalised(uploads: list[ImageUpload]) -> list[NormalisedImage]:
    images = []
    for upload in uploads:
        try:
            data = base64.b64decode(upload.data, validate=True)
        except binascii.Error as error:
            raise ImageRefusedError("an image was not valid base64") from error
        images.append(normalise(data))
    return images


# The stream's session work, each piece one short transaction off the event loop.


def _new_thread(
    session: Session, workspace_id: int, title: str, scope: SourceScope | None
) -> ChatThread:
    """Insert the thread; the id and timestamps come from the database."""
    thread = ChatThread(workspace_id=workspace_id, title=title)
    session.add(thread)
    session.flush()
    if scope is not None:
        store_thread_scope(session, thread, scope)
    session.refresh(thread)
    return thread


def _give_to_agent(session: Session, thread: ChatThread, session_id: str) -> None:
    """Record the opencode session that will hold the thread's turns.

    Reloaded here, off the event loop: the write moves `updated_at`, which the
    response reads.
    """
    thread.opencode_session_id = session_id
    session.flush()
    session.refresh(thread)


def _stored_turns(session: Session, thread: ChatThread) -> Sequence[ChatMessage]:
    """A chat thread's turns, oldest first."""
    return session.scalars(
        select(ChatMessage)
        .where(ChatMessage.chat_thread_id == thread.id)
        .order_by(ChatMessage.created_at)
    ).all()


def _ground(
    session: Session, thread: ChatThread, payload: MessageCreate
) -> tuple[ResolvedGeneration, Sequence[ChatMessage], list[Hit], dict]:
    """The model to answer with, the turns so far, the passages to cite, and
    what the user turn records of the sources it used."""
    try:
        resolved = resolve_generation(session)
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    # A sent scope is stored and used in this one transaction, so ticking a box
    # and pressing Enter cannot race. An explicit id list keeps today's meaning.
    scope = None
    record: dict = {}
    if payload.source_scope is not None:
        stored, scope = store_thread_scope(session, thread, payload.source_scope)
        record = scope.record(stored)
    elif payload.document_ids is not None:
        load_selected_sources(session, thread.workspace_id, payload.document_ids)
    else:
        stored = thread_scope(thread)
        scope = resolve_scope(session, thread.workspace_id, stored)
        record = scope.record(stored)
    # Keep numpy/onnxruntime lazy: only chat and ingestion need this module.
    from modules.embedding.encoder import missing_files

    if missing_files(require_active_index(session).spec):
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
        session,
        thread.workspace_id,
        payload.text,
        document_ids=payload.document_ids,
        scope=scope,
    )
    return resolved, history, hits, record


def _open_turn(
    session: Session,
    thread: ChatThread,
    text: str,
    images: list[NormalisedImage],
    scope_record: dict,
) -> tuple[ChatMessage, ChatMessage]:
    references = [
        store.store(image, thread.workspace_id, thread.id) for image in images
    ]
    # `images` only when there are some, so every row before them stays as it was.
    content: dict = {
        "text": text,
        **({"images": references} if references else {}),
        **scope_record,
    }
    user_message = ChatMessage(
        chat_thread_id=thread.id, role=MessageRole.USER, content=content
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


def _sweep_images(session: Session, thread: ChatThread) -> None:
    """Remove the files a discarded turn alone pointed at."""
    contents = session.scalars(
        select(ChatMessage.content).where(ChatMessage.chat_thread_id == thread.id)
    ).all()
    store.remove_unreferenced(
        thread.workspace_id, thread.id, store.referenced_keys(list(contents))
    )


def _rename(_session: Session, thread: ChatThread, title: str) -> None:
    thread.title = title


def _discard_turn(
    session: Session, user_message: ChatMessage, assistant_message: ChatMessage
) -> None:
    """A turn that produced no content at all leaves no trace, not a blank reply."""
    session.delete(assistant_message)
    session.delete(user_message)


def _complete(
    _session: Session,
    message: ChatMessage,
    answer: str,
    cited: list[dict],
    reasoning: dict | None,
) -> None:
    message.content = {"text": answer, "citations": cited}
    if reasoning is not None:
        message.content["reasoning"] = reasoning
    message.completed_at = datetime.now(UTC)


def _iso(instant: datetime) -> str:
    """Spelled as Pydantic spells the REST timestamps: UTC as Z."""
    return instant.isoformat().replace("+00:00", "Z")


async def _context_tokens_or_none(generator: Generator, model: str) -> int | None:
    """The model's window, or None on anything short of a clean answer.

    A transient failure to read it must not fail the turn: it only narrows how
    the prompt is budgeted, and the unknown-window fallback in
    `modules.chat.budget` is exactly today's behavior.
    """
    try:
        return await generator.context_tokens(model)
    except Exception:
        logger.warning("Could not read the context window for %s", model, exc_info=True)
        return None


def _token_counter(generator: Generator, model: str) -> TokenCounter:
    """A per-turn counter bound to this turn's model, defensive the same way
    `_context_tokens_or_none` is: a failure here only widens the heuristic
    `build_messages` already falls back to for that one turn, never the turn."""

    async def count(text: str) -> int | None:
        try:
            return await generator.token_count(model, text)
        except Exception:
            logger.warning("Could not count tokens for %s", model, exc_info=True)
            return None

    return count


def _frame(payload: dict) -> bytes:
    """One SSE data frame in the stream's accepted/delta/terminal protocol."""
    return f"data: {json.dumps(payload)}\n\n".encode()


_DONE = b"data: [DONE]\n\n"
