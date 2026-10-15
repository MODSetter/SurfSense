import uvicorn

from api.config import get_settings
from api.main import create_app
from shared.going_back.command_line import refuse_a_newer_database


def serve() -> None:
    """Run the API in the foreground; Electron supervises it as a sidecar."""
    refuse_a_newer_database()
    settings = get_settings()
    uvicorn.run(create_app(), host=settings.host, port=settings.port)
