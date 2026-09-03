import uvicorn

from api.config import get_settings
from api.main import create_app


def serve() -> None:
    """Run the API in the foreground; Electron supervises it as a sidecar."""
    settings = get_settings()
    uvicorn.run(create_app(), host=settings.host, port=settings.port)
