from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from modules.chat.router import router as chat_router
from modules.documents.router import router as documents_router
from modules.events.broker import EventBroker
from modules.events.router import router as events_router
from modules.health.router import router as health_router
from modules.llm.router import router as llm_router
from modules.workspaces.router import router as workspaces_router
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory, import_models
from shared.migrations import upgrade_to_head


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """The API owns migrations; the worker only ever reads and writes rows."""
    engine = create_db_engine(get_storage_settings().database_path)
    try:
        upgrade_to_head(engine)
        app.state.session_factory = create_session_factory(engine)
        yield
    finally:
        engine.dispose()


def create_app() -> FastAPI:
    """Application factory; each call returns an app isolated from the others."""
    import_models()

    app = FastAPI(title="SurfSense Community Local", lifespan=lifespan)
    app.state.broker = EventBroker() # No benefits from lifespan hooks.
    app.include_router(health_router)
    app.include_router(workspaces_router)
    app.include_router(documents_router)
    app.include_router(llm_router)
    app.include_router(chat_router)
    app.include_router(events_router)
    return app
