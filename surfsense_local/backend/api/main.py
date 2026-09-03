from fastapi import FastAPI

from modules.health.router import router as health_router


def create_app() -> FastAPI:
    """Application factory; each call returns an app isolated from the others."""
    app = FastAPI(title="SurfSense Community Local")
    app.include_router(health_router)
    return app
