import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from modules.artifacts.podcast.router import router as podcast_router
from modules.artifacts.router import router as artifacts_router
from modules.chat.router import router as chat_router
from modules.documents.router import router as documents_router
from modules.egress.router import router as egress_router
from modules.egress.service import EgressDeniedError
from modules.events.broker import EventBroker
from modules.events.router import router as events_router
from modules.health.router import router as health_router
from modules.license.router import router as license_router
from modules.llm.catalog.dependencies import get_catalog_service
from modules.llm.router import router as llm_router
from modules.migration.router import router as migration_router
from modules.workspaces.router import router as workspaces_router
from modules.workspaces.seed import ensure_default_workspace
from shared.config import get_storage_settings
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
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        upgrade_to_head(engine)
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            ensure_default_workspace(session)
            session.commit()
        app.state.session_factory = session_factory
        # The preset is derived from what is on disk, so rebuild it at boot
        # rather than only after an install. Without this a model imported from
        # disk, or installed before this existed, loads at llama.cpp's own
        # default window instead of the one the fit calculation chose, and a
        # stale section keeps advertising a model whose file is gone.
        _rewrite_generation_preset()
        yield
    finally:
        engine.dispose()


def _rewrite_generation_preset() -> None:
    """Best effort: a preset that cannot be written must not stop the API."""
    try:
        get_catalog_service().reprice()
    except Exception:
        logger.exception("could not rewrite the generation preset at startup")


def create_app() -> FastAPI:
    """Application factory; each call returns an app isolated from the others."""
    import_models()

    app = FastAPI(title="SurfSense Community Local", lifespan=lifespan)
    app.add_middleware(MarkRequest)
    # The packaged renderer loads from file:// and calls the 127.0.0.1 sidecar,
    # a cross-origin request; the API is loopback-only single-user, so allow any.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.broker = EventBroker()  # No benefits from lifespan hooks.
    app.include_router(health_router)
    app.include_router(workspaces_router)
    app.include_router(documents_router)
    app.include_router(llm_router)
    app.include_router(chat_router)
    app.include_router(artifacts_router)
    app.include_router(podcast_router)
    app.include_router(events_router)
    app.include_router(migration_router)
    app.include_router(license_router)
    app.include_router(egress_router)
    app.add_exception_handler(EgressDeniedError, egress_denied)
    app.add_exception_handler(UnreadableSecretError, unreadable_secret)
    return app


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


def egress_denied(_request: Request, error: EgressDeniedError) -> JSONResponse:
    return JSONResponse(
        {
            "detail": {
                "code": "egress_disabled",
                "message": str(error),
                "destination": error.destination,
                "host": error.host,
            }
        },
        status.HTTP_403_FORBIDDEN,
    )
