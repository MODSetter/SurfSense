import asyncio
import socket
import threading
from collections.abc import AsyncIterator, Iterator

import pytest
import uvicorn
from sqlalchemy import Engine

from api.main import create_app
from shared.config import get_license_server_settings
from tests.license_server_stand_in import StandInLicenseServer
from tests.mcp_test_server import serving


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def base_url(data_dir: object, engine: Engine) -> AsyncIterator[str]:
    """Serve a migrated app on a free port; data_dir points it at this test's DB,
    which `engine` has already built with the embedder fixed, as onboarding would."""
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture
def license_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[StandInLicenseServer]:
    """SurfSense's license server run locally, as a developer's build points at it."""
    stand_in = StandInLicenseServer()
    with serving(stand_in.app()) as base:
        monkeypatch.setattr(get_license_server_settings(), "license_server_url", base)
        yield stand_in


@pytest.fixture
def compiled_license_server(monkeypatch: pytest.MonkeyPatch) -> None:
    """The build's own server, api.surfsense.com, whatever this machine's environment says."""
    monkeypatch.setattr(get_license_server_settings(), "license_server_url", None)
