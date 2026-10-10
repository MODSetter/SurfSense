import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[6] / "surfsense_local" / "backend"

# The app as a user has it once onboarding is done: plugins run only after it,
# so the embedder is fixed (bge-small, the default) before the API starts.
SERVE_ONBOARDED = (
    "from modules.embedding.lock import lock_default_if_unchosen; "
    "from shared.config import get_storage_settings; "
    "from shared.db import create_db_engine, create_session_factory, import_models; "
    "from shared.migrations import upgrade_to_head; "
    "import_models(); "
    "engine = create_db_engine(get_storage_settings().database_path); "
    "upgrade_to_head(engine); "
    "session = create_session_factory(engine)(); "
    "lock_default_if_unchosen(session); session.commit(); session.close(); "
    "engine.dispose(); "
    "from api.server import serve; serve()"
)

# A first `uv run` may still be installing the backend's own packages.
STARTUP_SECONDS = 180


@dataclass
class RealApp:
    """The app's real API, which the SDK's verbs must keep working against."""

    url: str

    def call(self, method: str, path: str, body: object = None) -> object:
        """Calls the app the way any client does, to set up or check a test."""
        request = urllib.request.Request(
            self.url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={} if body is None else {"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"null")

    def new_workspace(self) -> int:
        """A workspace of the test's own, so no test sees another's documents."""
        created = self.call("POST", "/workspaces", {"name": "Contract test"})
        return int(created["id"])  # type: ignore[index]

    def context(self, workspace_id: int) -> dict[str, str]:
        """The environment the app's runner gives a plugin run in that workspace."""
        return {
            "SURFSENSE_PLUGIN_API_URL": self.url,
            "SURFSENSE_PLUGIN_WORKSPACE_ID": str(workspace_id),
            "SURFSENSE_PLUGIN_RUN_ID": "41",
            "SURFSENSE_PLUGIN_ID": "example",
        }


def _free_port() -> int:
    """A port nothing listens on, for this session's app."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _answers(url: str) -> bool:
    """Whether the app is up: /health answers once migrations have run."""
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


@pytest.fixture(scope="session")
def real_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RealApp]:
    """The backend started on a data folder of its own, as Electron starts it."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail(
            "the contract tests start the backend with uv, which is not on PATH"
        )

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    log = tmp_path_factory.mktemp("app") / "app.log"
    # The SDK's own virtual environment is not the backend's.
    environment = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"} | {
        "SURFSENSE_LOCAL_DATA_DIR": str(tmp_path_factory.mktemp("app-data")),
        "SURFSENSE_LOCAL_SECRET": "contract-tests",
        "SURFSENSE_LOCAL_HOST": "127.0.0.1",
        "SURFSENSE_LOCAL_PORT": str(port),
    }
    with log.open("w") as output:
        app = subprocess.Popen(
            [
                uv,
                "run",
                "--directory",
                str(BACKEND_DIR),
                "python",
                "-c",
                SERVE_ONBOARDED,
            ],
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    try:
        deadline = time.monotonic() + STARTUP_SECONDS
        while not _answers(url):
            if app.poll() is not None or time.monotonic() > deadline:
                pytest.fail(f"the app did not start:\n{log.read_text()[-3000:]}")
            time.sleep(0.5)
        yield RealApp(url)
    finally:
        app.terminate()
        try:
            app.wait(timeout=15)
        except subprocess.TimeoutExpired:
            app.kill()
