import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack

import anyio
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from modules.llm.activity import model_activity, model_key
from modules.llm.admission.waiting import wait_in_line
from modules.llm.catalog.remote.context_window import remote_context_window
from modules.llm.model_route.failures import as_frame
from modules.llm.model_route.keep_alive import with_keep_alive
from modules.llm.model_route.schemas import (
    GenerateRequest,
    ModelRef,
    WindowReply,
    WindowRequest,
)
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from modules.llm.providers import llamacpp
from modules.llm.providers.llamacpp.router_client import RouterClient
from modules.llm.providers.llamacpp.unload import unload_text_models
from modules.llm.resolution import (
    ModelResolutionError,
    ResolvedGeneration,
    resolve_generation,
    resolve_generation_of,
)
from shared.config import get_llm_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["llm"])

_DONE = b"data: [DONE]\n\n"


@router.post(
    "/internal/models/text/generate",
    summary="Generate text for another process (loopback only)",
)
async def generate(payload: GenerateRequest, request: Request) -> StreamingResponse:
    """The one way a process other than the API generates text.

    The API resolves the model, checks egress, marks it in use and, on the local
    runtime, admits the request beside chat, so nothing reaches a model it does
    not count. `409` for a model that can no longer be resolved.
    """
    try:
        resolved = await run_in_threadpool(
            _resolve, request.app.state.session_factory, payload.model
        )
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    selected = resolved.selection
    local = selected.provider == llamacpp.PROVIDER
    if local and not await _installed(selected.name):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "the local model is no longer installed"
        )
    activity_key = model_key(selected.provider, selected.name, selected.connection_id)
    admission = request.app.state.local_admission
    messages = [message.as_message() for message in payload.messages]

    async def frames() -> AsyncIterator[bytes]:
        # Marked in use here, not before the response: Starlette never runs a
        # body the caller left before it started, so a mark taken outside would
        # never be released.
        in_use = False
        try:
            await model_activity.acquire_use(activity_key)
            in_use = True
            async with AsyncExitStack() as held:
                if local:
                    async for place in wait_in_line(
                        held,
                        lambda tell: admission.admitted(
                            selected.name,
                            messages,
                            payload.max_tokens,
                            payload.priority.priority(),
                            tell,
                        ),
                    ):
                        yield _frame({"type": "queued", "position": place})
                async for text in resolved.generator.chat(
                    selected.name,
                    messages,
                    max_tokens=payload.max_tokens,
                    temperature=payload.temperature,
                    reasoning=payload.reasoning,
                    json_schema=payload.json_schema,
                    conversation=payload.conversation,
                ):
                    yield _frame({"type": "text", "text": text})
        except Exception as failure:
            yield _frame(as_frame(failure))
        finally:
            if in_use:
                with anyio.CancelScope(shield=True):
                    await model_activity.release_use(activity_key)
        yield _DONE

    return StreamingResponse(
        with_keep_alive(frames()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/internal/models/text/window",
    summary="The window a text model answers within (loopback only)",
)
async def window(payload: WindowRequest, request: Request) -> WindowReply:
    """What a caller sizes a prompt from: the window llama-server loaded a local
    model with, which may load it, or what a remote model's plan or the remote
    catalog states. `null` when nothing states it. `409` as `generate` answers it.
    """
    try:
        resolved, catalog_provider = await run_in_threadpool(
            _resolve_with_catalog, request.app.state.session_factory, payload.model
        )
    except ModelResolutionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    selected = resolved.selection
    admission = request.app.state.local_admission
    # Nothing may load a text model under an image's hold, so the last reading stands.
    if selected.provider == llamacpp.PROVIDER and admission.held:
        return WindowReply(window=admission.last_window(selected.name))
    try:
        stated = await resolved.generator.context_tokens(selected.name)
    except Exception:
        logger.warning("could not read the window of %s", selected.name, exc_info=True)
        stated = None
    if stated is None and selected.provider != llamacpp.PROVIDER:
        stated = remote_context_window(selected.name, catalog_provider)
    return WindowReply(window=stated)


@router.post(
    "/internal/models/text/yield",
    summary="Hold the local runtime free of text, for an image (loopback only)",
)
async def give_up_runtime(request: Request) -> StreamingResponse:
    """Unload the text models once nothing is generating, and keep text out
    until the caller closes this request.

    Held open for as long as local image generation needs the graphics card.
    Local text sent meanwhile waits in line; a caller that dies drops the
    connection, which releases the hold. Speech recognition gives its memory
    back too, and starts no recording's window until then.
    """
    admission = request.app.state.local_admission
    transcription = request.app.state.transcription_gate

    async def frames() -> AsyncIterator[bytes]:
        async with transcription.text_runtime_held(), admission.given_up():
            await unload_text_models(RouterClient(get_llm_settings().llamacpp_base_url))
            yield _frame({"type": "yielded"})
            await asyncio.Event().wait()

    return StreamingResponse(
        with_keep_alive(frames()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _resolve(
    session_factory: sessionmaker[Session], model: ModelRef | None
) -> ResolvedGeneration:
    with session_factory() as session:
        return _resolved(session, model)


def _resolve_with_catalog(
    session_factory: sessionmaker[Session], model: ModelRef | None
) -> tuple[ResolvedGeneration, str | None]:
    """The model, and the catalog provider its connection names."""
    with session_factory() as session:
        resolved = _resolved(session, model)
        connection_id = resolved.selection.connection_id
        connection = (
            session.get(ProviderConnection, connection_id) if connection_id else None
        )
        return resolved, connection.catalog_provider if connection else None


def _resolved(session: Session, model: ModelRef | None) -> ResolvedGeneration:
    if model is None:
        return resolve_generation(session)
    named = SelectedModel(
        model_type=ModelType.TEXT_GEN,
        provider=model.provider,
        name=model.name,
        connection_id=model.connection_id,
    )
    return resolve_generation_of(session, named)


async def _installed(name: str) -> bool:
    """Whether the local runtime still lists the model, loaded or not."""
    try:
        listed = await RouterClient(get_llm_settings().llamacpp_base_url).models()
    except Exception:
        # The runtime's own error says more than a guess here would.
        return True
    return any(model.id == name for model in listed)


def _frame(payload: dict) -> bytes:
    return f"data: {json.dumps(payload)}\n\n".encode()
