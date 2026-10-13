import base64
import contextlib
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[5] / "surfsense_local" / "backend"

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


def example_manifest() -> dict:
    """A small plugin with one action, which each test changes what it needs in."""
    return {
        "id": "example",
        "name": "Example",
        "description": "Echoes its input.",
        "author": "SurfSense",
        "access": "free",
        "hosts": [],
        "actions": [
            {
                "name": "echo",
                "title": "Echo",
                "inputs": [
                    {"name": "text", "title": "Text", "kind": "string"},
                ],
            }
        ],
    }


@dataclass
class Plugin:
    """A plugin folder an author is working on, outside the repository's plugins/."""

    folder: Path
    manifest: dict = field(default_factory=example_manifest)

    def write(self, main: str, files: dict[str, str] | None = None) -> None:
        """Lays down the plugin's files, its manifest.json included."""
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / "manifest.json").write_text(json.dumps(self.manifest))
        (self.folder / "main.py").write_text(main)
        for relative, text in (files or {}).items():
            path = self.folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)


@pytest.fixture
def plugin(tmp_path: Path) -> Plugin:
    """An example plugin folder for a test to write and invoke."""
    return Plugin(folder=tmp_path / "plugins" / "example")


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A home folder of the test's own, so no test reads the author's ~/.surfsense."""
    folder = tmp_path / "home"
    folder.mkdir()
    return folder


@pytest.fixture
def cli(home: Path) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Runs surfsense-plugins as an author would, in a home of its own."""

    def run(
        *arguments: str,
        environment: dict[str, str] | None = None,
        typed: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """One call of the command, with what the author typed at any prompt."""
        return subprocess.run(
            [sys.executable, "-m", "surfsense_plugin_cli", *arguments],
            env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
            | {"HOME": str(home), "USERPROFILE": str(home)}
            | (environment or {}),
            input=typed,
            capture_output=True,
            text=True,
            timeout=300,
        )

    return run


@dataclass
class RealApp:
    """The app's real API, which invoke runs plugins against."""

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
        created = self.call("POST", "/workspaces", {"name": "CLI test"})
        return int(created["id"])  # type: ignore[index]


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


@contextlib.contextmanager
def _started_app(folder: Path) -> Iterator[RealApp]:
    """The backend on a data folder of its own, as Electron starts it."""
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("these tests start the backend with uv, which is not on PATH")

    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    log = folder / "app.log"
    environment = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"} | {
        "SURFSENSE_LOCAL_DATA_DIR": str(folder / "data"),
        "SURFSENSE_LOCAL_SECRET": "cli-tests",
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


@pytest.fixture(scope="session")
def real_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[RealApp]:
    """One app for the session: each test makes the workspaces it needs."""
    with _started_app(tmp_path_factory.mktemp("app")) as app:
        yield app


@pytest.fixture
def fresh_app(tmp_path: Path) -> Iterator[RealApp]:
    """An app as first installed: its one default workspace and nothing else."""
    with _started_app(tmp_path) as app:
        yield app


ADDS_A_NOTE = """
from surfsense_plugin_sdk import action, document


@action("echo")
def echo(text: str) -> None:
    print(document.add(title="Echo", content=text).id)
"""


@pytest.fixture
def plugin_that_adds_a_note(plugin: Plugin) -> Plugin:
    """The example plugin, printing the id of the note it adds."""
    plugin.write(ADDS_A_NOTE)
    return plugin


@dataclass
class Wheels:
    """A folder of wheels the test builds, standing in for PyPI."""

    folder: Path

    def make(
        self, name: str, version: str, files: dict[str, str], tag: str = "py3-none-any"
    ) -> Path:
        """A wheel holding these files, for the platforms its tag names."""
        dist = f"{name.replace('-', '_')}-{version}"
        wheel = self.folder / f"{dist}-{tag}.whl"
        entries = dict(files) | {
            f"{dist}.dist-info/METADATA": (
                f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
            ),
            f"{dist}.dist-info/WHEEL": (
                "Wheel-Version: 1.0\nGenerator: tests\n"
                f"Root-Is-Purelib: {'true' if tag.endswith('any') else 'false'}\n"
                f"Tag: {tag}\n"
            ),
        }
        record = [
            f"{path},sha256={_digest(text.encode())},{len(text.encode())}"
            for path, text in entries.items()
        ]
        entries[f"{dist}.dist-info/RECORD"] = "\n".join(
            [*record, f"{dist}.dist-info/RECORD,,"]
        )
        with zipfile.ZipFile(wheel, "w") as archive:
            for path, text in entries.items():
                archive.writestr(path, text)
        return wheel

    @property
    def environment(self) -> dict[str, str]:
        """What points uv at this folder and nowhere else."""
        return {"UV_OFFLINE": "1", "UV_FIND_LINKS": str(self.folder)}


def _digest(content: bytes) -> str:
    """A RECORD line's hash: urlsafe base64 of the sha256, without padding."""
    return (
        base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode()
    )


@pytest.fixture
def wheels(tmp_path: Path) -> Wheels:
    """An empty folder of wheels for the test to fill."""
    folder = tmp_path / "wheels"
    folder.mkdir()
    return Wheels(folder)
