from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from modules.health.router import router as health_router
from shared.config import get_storage_settings
from shared.db import create_db_engine, create_session_factory
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
    app = FastAPI(title="SurfSense Community Local", lifespan=lifespan)
    app.include_router(health_router)
    return app
