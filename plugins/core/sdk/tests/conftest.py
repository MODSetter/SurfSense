import contextlib
import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SDK_DIR = Path(__file__).resolve().parents[1]

# What the app's runner hands a plugin besides its context, per the protocol.
# PYTHONSAFEPATH keeps the plugin's folder, the working directory, off the path.
RUNNER_ENVIRONMENT = {
    "PYTHONPATH": str(SDK_DIR),
    "PYTHONSAFEPATH": "1",
    "PYTHONNOUSERSITE": "1",
    "PYTHONUTF8": "1",
    "PYTHONUNBUFFERED": "1",
}

# What Windows needs for Python to start at all.
WINDOWS_ENVIRONMENT = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")


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
    """A plugin folder on disk, run the way the app's runner runs it."""

    folder: Path
    data: Path
    manifest: dict = field(default_factory=example_manifest)

    def write(self, main: str, files: dict[str, str] | None = None) -> None:
        """Lays down the plugin's files, its manifest.json included."""
        (self.folder / "manifest.json").write_text(json.dumps(self.manifest))
        (self.folder / "main.py").write_text(main)
        for relative, text in (files or {}).items():
            path = self.folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def run(
        self,
        action: str,
        inputs: dict | None = None,
        context: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Runs an action as the app's runner will: its own process and environment."""
        inputs_file = self.folder.parent / "inputs.json"
        inputs_file.write_text(json.dumps(inputs or {}))
        environment = {
            "PATH": os.environ["PATH"],
            **{
                name: os.environ[name]
                for name in WINDOWS_ENVIRONMENT
                if name in os.environ
            },
            **RUNNER_ENVIRONMENT,
            **(context or {}),
        }
        return subprocess.run(
            [
                sys.executable,
                "-S",
                "-m",
                "surfsense_plugin_sdk.run",
                str(self.folder),
                action,
                "--inputs",
                str(inputs_file),
                "--data",
                str(self.data),
            ],
            cwd=self.folder,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )


@pytest.fixture
def plugin(tmp_path: Path) -> Plugin:
    """An empty plugin folder and its data folder, for a test to write and run."""
    folder = tmp_path / "example"
    data = tmp_path / "data"
    folder.mkdir()
    data.mkdir()
    return Plugin(folder=folder, data=data)


@dataclass
class Received:
    """One request the stub got, as a test asserts on it."""

    method: str
    path: str
    headers: dict[str, str]
    body: object


@dataclass
class StubApp:
    """The app's API as a plugin sees it: canned answers, and every request kept."""

    url: str = ""
    port: int = 0
    received: list[Received] = field(default_factory=list)
    answers: dict[tuple[str, str], tuple[int, object, dict[str, str]]] = field(
        default_factory=dict
    )

    def answer(
        self,
        method: str,
        path: str,
        status: int,
        body: object,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Sets what the stub replies to one method and path."""
        self.answers[(method, path)] = (status, body, headers or {})

    def context(self, **overrides: str) -> dict[str, str]:
        """The environment the runner gives a plugin started in workspace 7."""
        return {
            "SURFSENSE_PLUGIN_API_URL": self.url,
            "SURFSENSE_PLUGIN_WORKSPACE_ID": "7",
            "SURFSENSE_PLUGIN_RUN_ID": "41",
            "SURFSENSE_PLUGIN_ID": "example",
            **overrides,
        }


@contextlib.contextmanager
def _serving() -> Iterator[StubApp]:
    """A real HTTP server on a free loopback port, stopped when the test ends."""
    stub = StubApp()

    class Handler(BaseHTTPRequestHandler):
        """Records each request, then replies with its canned answer."""

        def _serve(self) -> None:
            """Every method alike: record, then answer."""
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            stub.received.append(
                Received(
                    self.command,
                    self.path,
                    dict(self.headers.items()),
                    json.loads(raw) if raw else None,
                )
            )
            status, body, headers = stub.answers.get(
                (self.command, self.path), (404, {"detail": "Not Found"}, {})
            )
            encoded = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(encoded)

        # The names BaseHTTPRequestHandler dispatches on.
        do_GET = do_POST = do_PATCH = _serve  # noqa: N815

        def log_message(self, *_: object) -> None:
            """Keeps test output to what the plugin itself wrote."""
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    stub.port = server.server_port
    stub.url = f"http://127.0.0.1:{stub.port}"
    # A short poll, or shutdown waits half a second for every test.
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    thread.start()
    yield stub
    server.shutdown()
    server.server_close()


@pytest.fixture
def app() -> Iterator[StubApp]:
    """The app's API, reached through SURFSENSE_PLUGIN_API_URL."""
    with _serving() as stub:
        yield stub


@pytest.fixture
def source() -> Iterator[StubApp]:
    """A site a plugin fetches from, declared in its manifest as localhost."""
    with _serving() as stub:
        yield stub
