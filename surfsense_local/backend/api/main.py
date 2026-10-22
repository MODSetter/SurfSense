import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker
from starlette.types import ASGIApp, Receive, Scope, Send

from api.config import Settings, get_settings
from modules.agent.agent_threads.router import router as agent_threads_router
from modules.agent.engines.thread_engine import close_engines
from modules.agent.launch_key import mint_launch_key
from modules.agent.model_endpoint.responses_relay.router import (
    router as agent_responses_router,
)
from modules.agent.model_endpoint.router import router as agent_model_router
from modules.agent.plugin_gateway.router import router as agent_plugins_router
from modules.agent.plugin_tools.router import router as plugin_steps_router
from modules.agent.previews.router import file_router as agent_preview_files_router
from modules.agent.previews.router import router as agent_previews_router
from modules.agent.runtime_proxy.server import serving_runtime_proxy
from modules.agent.tool_endpoint.router import router as agent_tools_router
from modules.artifacts.podcast.router import router as podcast_router
from modules.artifacts.router import router as artifacts_router
from modules.artifacts.studio_documents.router import router as refine_router
from modules.chat.interrupted_turns import settle_interrupted_turns
from modules.chat.router import router as chat_router
from modules.chat.runs.registry import ChatRuns
from modules.chat.runs.router import router as chat_runs_router
from modules.documents.router import router as documents_router
from modules.documents.web_sources.router import router as web_sources_router
from modules.egress.router import router as egress_router
from modules.egress.service import EgressDeniedError
from modules.embedding.active import EmbeddingNotChosenError
from modules.embedding.huggingface.router import (
    router as embedding_huggingface_router,
)
from modules.embedding.router import router as embedding_router
from modules.events.broker import EventBroker
from modules.events.router import router as events_router
from modules.folders.finish_deletes import finish_interrupted_deletes
from modules.folders.router import router as folders_router
from modules.health.router import router as health_router
from modules.license.router import router as license_router
from modules.llm.admission.local_runtime import LocalAdmission
from modules.llm.catalog.local.dependencies import get_local_catalog
from modules.llm.default_voice import choose_default_voice
from modules.llm.model_route.router import router as model_route_router
from modules.llm.model_type import ModelType
from modules.llm.models import SelectedModel
from modules.llm.residency import warm_selected
from modules.llm.router import router as llm_router
from modules.llm.subscriptions.claude.errors import (
    ClaudeSignInRequiredError,
    ClaudeTooOldError,
)
from modules.llm.subscriptions.claude.plan_generator import close_claude_runs
from modules.llm.subscriptions.claude.proxy import serving_claude_proxy
from modules.llm.transcription.gate import TranscriptionGate
from modules.llm.transcription.internal_router import (
    router as transcription_windows_router,
)
from modules.llm.transcription.server import unload_speech_model
from modules.llm.transcription.sessions import DictationSessions
from modules.migration.router import router as migration_router
from modules.plugins.license_verdict.routes import router as plugin_license_router
from modules.plugins.lists.registry.routes import router as plugin_registry_router
from modules.plugins.remote.sign_in.oauth.routes import router as plugin_oauth_router
from modules.plugins.routes import router as plugins_router
from modules.resource_usage.router import router as resource_usage_router
from modules.runtime_packs.office.router import router as office_pack_router
from modules.source_scope.router import router as source_scope_router
from modules.usage_statistics.activity_counts import begin_counting
from modules.usage_statistics.router import router as usage_statistics_router
from modules.workspaces.router import router as workspaces_router
from modules.workspaces.seed import ensure_default_workspace
from shared.config import get_agent_settings, get_llm_settings, get_storage_settings
from shared.db import (
    create_db_engine,
    create_session_factory,
    import_models,
    serving_request,
)
from shared.migrations import upgrade_to_head
from shared.secrets import UnreadableSecretError


class MarkRequest:
    """Flag the span of each HTTP request, so shared.db can refuse a SQLite
    transaction opened on the event loop. Lifespan work stays unflagged: it
    runs alone, before any request could be stalled by it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        token = serving_request.set(scope["type"] == "http")
        try:
            await self.app(scope, receive, send)
        finally:
            serving_request.reset(token)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """The API owns migrations; the worker only ever reads and writes rows."""
    storage = get_storage_settings()
    engine = create_db_engine(storage.database_path)
    try:
        upgrade_to_head(engine, backups_dir=storage.data_dir / "backups")
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            ensure_default_workspace(session)
            settle_interrupted_turns(session)
            session.commit()
            begin_counting(session)
        app.state.session_factory = session_factory
        # A thread too: a large subtree takes a while, and it is out of every
        # scope and the tree meanwhile.
        threading.Thread(
            target=_finish_folder_deletes,
            args=(session_factory,),
            name="folder-deletes",
            daemon=True,
        ).start()
        # Off the startup path, on a thread. Both halves are slow for the same
        # reason: the preset is priced against the devices, and taking the
        # device probe costs about 19 seconds on a Mac the first time, while
        # Metal compiles its shader libraries. Done here, /health would not
        # answer until it finished.
        #
        # The preset itself is rebuilt at boot rather than only after an
        # install, because without it a model imported from disk loads at
        # llama.cpp's own default window instead of the one the fit calculation
        # chose, and a stale section keeps advertising a model whose file is
        # gone.
        threading.Thread(
            target=_warm_catalog,
            args=(session_factory,),
            name="catalog-warm",
            daemon=True,
        ).start()
        async with (
            _opencode_proxy(session_factory),
            serving_claude_proxy(session_factory, get_settings().host),
        ):
            yield
    finally:
        await close_claude_runs()
        await close_engines()
        engine.dispose()


@asynccontextmanager
async def _opencode_proxy(
    session_factory: sessionmaker[Session],
) -> AsyncIterator[None]:
    """Where opencode's proxy variables point, beside an opencode only; it refuses every host."""
    agent = get_agent_settings()
    if not agent.has_opencode() or agent.opencode_proxy_port is None:
        yield
        return
    host = get_settings().host
    async with serving_runtime_proxy(session_factory, host, agent.opencode_proxy_port):
        yield


def _finish_folder_deletes(session_factory: sessionmaker[Session]) -> None:
    try:
        finish_interrupted_deletes(session_factory)
    except Exception:
        logger.exception("could not finish the folder deletes left at startup")


def _warm_catalog(session_factory: sessionmaker[Session]) -> None:
    """Best effort: neither the probe nor the preset may stop the API.

    A daemon thread, so a probe wedged on a driver call cannot hold shutdown
    open. A request arriving meanwhile waits on the service's own lock rather
    than starting a second probe.
    """
    try:
        get_local_catalog().warm()
    except Exception:
        logger.exception("could not warm the model catalog at startup")
        return

    try:
        with session_factory() as session:
            asyncio.run(choose_default_voice(session))
    except Exception:
        logger.exception("could not choose the shipped voice at startup")

    # Then the model itself, in that order: pricing the preset first is what
    # decides the window the load will use, and a load started before it would
    # take llama.cpp's own default and have to be redone.
    #
    # Nothing is resident after a restart whatever the idle policy is, so
    # without this the first question of every session pays a cold load with
    # nothing on screen to say why.
    try:
        with session_factory() as session:
            selected = session.get(SelectedModel, ModelType.TEXT_GEN)
        asyncio.run(warm_selected(selected, get_llm_settings().llamacpp_base_url))
    except Exception:
        logger.exception("could not warm the selected model at startup")


def add_cors(app: FastAPI, settings: Settings) -> None:
    """An empty origin list makes CORSMiddleware add no headers at all."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_methods=["*"],
        allow_headers=["*"],
    )


def create_app() -> FastAPI:
    """Application factory; each call returns an app isolated from the others."""
    import_models()

    app = FastAPI(title="SurfSense Community Local", lifespan=lifespan)
    app.add_middleware(MarkRequest)
    add_cors(app, get_settings())
    app.state.broker = EventBroker()  # No benefits from lifespan hooks.
    app.state.chat_runs = ChatRuns()
    app.state.local_admission = LocalAdmission()
    app.state.dictations = DictationSessions()
    app.state.transcription_gate = TranscriptionGate(
        dictating=app.state.dictations.any_open, unload=unload_speech_model
    )
    # Written into opencode's configuration; this process's turns only.
    app.state.agent_launch_key = mint_launch_key()
    app.include_router(health_router)
    app.include_router(workspaces_router)
    app.include_router(documents_router)
    app.include_router(web_sources_router)
    app.include_router(folders_router)
    app.include_router(llm_router)
    app.include_router(model_route_router)
    app.include_router(transcription_windows_router)
    app.include_router(chat_router)
    app.include_router(chat_runs_router)
    app.include_router(source_scope_router)
    app.include_router(artifacts_router)
    app.include_router(podcast_router)
    app.include_router(refine_router)
    app.include_router(events_router)
    app.include_router(migration_router)
    app.include_router(license_router)
    app.include_router(egress_router)
    app.include_router(embedding_router)
    app.include_router(embedding_huggingface_router)
    app.include_router(resource_usage_router)
    app.include_router(usage_statistics_router)
    app.include_router(office_pack_router)
    # Before `/plugins/{id}/...`, which would otherwise take `registry` or `license` for an id.
    app.include_router(plugin_registry_router)
    app.include_router(plugin_license_router)
    app.include_router(plugin_oauth_router)
    app.include_router(plugins_router)
    # Whichever engine runs a thread calls its tools and is answered through these.
    app.include_router(agent_tools_router)
    app.include_router(agent_plugins_router)
    app.include_router(agent_threads_router)
    app.include_router(plugin_steps_router)
    # Routes only opencode calls, or that answer it, exist only beside one.
    if get_agent_settings().has_opencode():
        app.include_router(agent_model_router)
        app.include_router(agent_responses_router)
        app.include_router(agent_previews_router)
        app.include_router(agent_preview_files_router)
    app.add_exception_handler(EgressDeniedError, egress_denied)
    app.add_exception_handler(EmbeddingNotChosenError, embedding_not_chosen)
    app.add_exception_handler(UnreadableSecretError, unreadable_secret)
    app.add_exception_handler(ClaudeTooOldError, claude_too_old)
    app.add_exception_handler(ClaudeSignInRequiredError, claude_sign_in_required)
    return app


def claude_too_old(_request: Request, error: ClaudeTooOldError) -> JSONResponse:
    """Handled once, here: the model list, a chat and an agent turn refuse it alike, before anything runs.

    409 like `unreadable_secret`: the request is fine; the user's Claude Code is not.
    """
    return JSONResponse(
        {"detail": {"code": "claude_too_old", "message": str(error)}},
        status.HTTP_409_CONFLICT,
    )


def claude_sign_in_required(
    _request: Request, error: ClaudeSignInRequiredError
) -> JSONResponse:
    """Claude Code gone before a run starts: the code the composer's model check already shows."""
    return JSONResponse(
        {"detail": {"code": "claude_sign_in_required", "message": str(error)}},
        status.HTTP_409_CONFLICT,
    )


def unreadable_secret(_request: Request, error: UnreadableSecretError) -> JSONResponse:
    """Handled once, here, because any route touching a stored key can hit it.

    409 rather than 500: the request is well formed and the server is healthy.
    What is wrong is a stored value, and the client is the one that can replace
    it.
    """
    return JSONResponse(
        {"detail": {"code": "unreadable_secret", "message": str(error)}},
        status.HTTP_409_CONFLICT,
    )


def embedding_not_chosen(
    _request: Request, error: EmbeddingNotChosenError
) -> JSONResponse:
    """Before onboarding fixes the embedder, nothing that would be embedded is taken."""
    return JSONResponse(
        {"detail": {"code": "embedding_not_chosen", "message": str(error)}},
        status.HTTP_409_CONFLICT,
    )


def egress_denied(_request: Request, error: EgressDeniedError) -> JSONResponse:
    return JSONResponse(
        {
            "detail": {
                "code": "egress_disabled",
                "message": str(error),
                "destination": error.destination,
                "host": error.host,
                "hosts": error.hosts,
                "purpose": error.purpose,
            }
        },
        status.HTTP_403_FORBIDDEN,
    )
