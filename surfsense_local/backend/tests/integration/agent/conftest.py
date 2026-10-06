import json
import os
import secrets
import threading
from collections import Counter, OrderedDict
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from api.config import get_settings
from api.main import create_app
from modules.agent.agent_threads import live_instances
from modules.agent.opencode_client import OpencodeClient
from modules.agent.opencode_config import AgentSetup, write_opencode_config
from modules.agent.tool_endpoint import failed_renders
from modules.llm.admission.local_runtime import LocalAdmission
from modules.llm.model_type import ModelType
from modules.llm.models import ProviderConnection, SelectedModel
from shared.config import get_agent_settings, get_llm_settings, get_storage_settings
from shared.db import create_db_engine, create_session_factory
from shared.queue import studio_queue
from tests.integration.agent.opencode_harness import (
    MODEL,
    RunningOpencode,
    ScriptedHandler,
    ScriptedModel,
    StandInForElectron,
    free_port,
    needs_staged_opencode,
    start_opencode,
    wait_until_healthy,
)
from tests.integration.agent.tool_endpoint_client import ToolEndpoint, endpoint_over

# OpenAI's sign-in and plan endpoints, faked, for a ChatGPT plan the relay reaches.
from tests.integration.llm.chatgpt.conftest import fake_openai  # noqa: F401

# The catalog records it as calling tools for the provider the connection names,
# so a thread opened with it is the agent's; the scripted model answers in its place.
AGENT_MODEL = "gpt-4o-mini"


@dataclass
class Received:
    """One request the model server was sent, as it arrived."""

    path: str
    headers: dict[str, str]
    body: dict


@dataclass
class StubModel:
    """An OpenAI-compatible model server: records each request, answers as told."""

    url: str = ""
    requests: list[Received] = field(default_factory=list)
    status: int = 200
    # The SSE `data:` payloads a streamed reply carries, `[DONE]` included or not.
    frames: list[str] = field(
        default_factory=lambda: [
            json.dumps({"choices": [{"delta": {"content": "Hello"}}]}),
            json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
            "[DONE]",
        ]
    )
    # Sent instead of the frames when `status` is an error.
    error_body: str = ""


class _Handler(BaseHTTPRequestHandler):
    """Answers `POST …/chat/completions` from the stub the server carries."""

    def do_POST(self) -> None:
        stub: StubModel = self.server.stub  # type: ignore[attr-defined]
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        stub.requests.append(Received(self.path, dict(self.headers), json.loads(raw)))
        if stub.status >= 400:
            body = stub.error_body.encode()
            self.send_response(stub.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for frame in stub.frames:
            self.wfile.write(f"data: {frame}\n\n".encode())
            self.wfile.flush()

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture(autouse=True)
def beside_an_opencode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build every app here as Electron starts one beside an opencode, so it has the agent's routes.

    Nothing listens on port 9; a test that runs opencode sets its own address.
    """
    monkeypatch.setattr(get_agent_settings(), "opencode_url", "http://127.0.0.1:9")
    monkeypatch.setattr(
        get_agent_settings(), "opencode_password", "not-a-running-opencode"
    )


@pytest.fixture(autouse=True)
def no_failed_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test's database gives out thread ids from 1 again; a turn's count must not carry over."""
    monkeypatch.setattr(failed_renders, "_failed", {})


@pytest.fixture(autouse=True)
def no_live_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts its own opencode: another test's instances are not in it to free."""
    monkeypatch.setattr(live_instances, "_used", OrderedDict())
    monkeypatch.setattr(live_instances, "_turns", Counter())


# MAX_PATH less its terminator: the most a path may hold where long paths are off.
MAX_PATH = 259


@pytest.fixture
def long_paths_off(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Windows without long paths: a longer path is not found. Collects each one tried."""
    too_long: list[str] = []

    def within_max_path(call):
        def checked(*paths: object, **kwargs: object):
            for path in paths:
                if isinstance(path, str | os.PathLike) and len(str(path)) > MAX_PATH:
                    too_long.append(str(path))
                    raise FileNotFoundError(3, "The path is too long", str(path))
            return call(*paths, **kwargs)

        return checked

    monkeypatch.setattr(os, "link", within_max_path(os.link))
    monkeypatch.setattr(os, "replace", within_max_path(os.replace))
    monkeypatch.setattr(Path, "write_bytes", within_max_path(Path.write_bytes))
    return too_long


@pytest.fixture
def model_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[StubModel]:
    """A real model server on a real port, which llama-server's address points at."""
    stub = StubModel()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.stub = stub  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stub.url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", stub.url)

    yield stub

    server.shutdown()
    server.server_close()


@pytest.fixture
def scripted_model() -> Iterator[ScriptedModel]:
    """A model on a real port that opencode's provider is pointed at."""
    model = ScriptedModel()
    server = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedHandler)
    server.model = model  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    model.url = f"http://127.0.0.1:{server.server_port}"
    yield model
    model.release.set()
    server.shutdown()
    server.server_close()


@pytest.fixture
def opencode(
    tmp_path: Path, scripted_model: ScriptedModel
) -> Iterator[RunningOpencode]:
    """The staged opencode on SurfSense's own configuration, its model scripted."""
    needs_staged_opencode()
    agent_dir = tmp_path / "agent"
    setup = AgentSetup(
        model=MODEL,
        window=32768,
        reads_images=False,
        endpoint_url=f"{scripted_model.url}/v1",
        launch_key="launch-key",
        route="chat_completions",
    )
    write_opencode_config(agent_dir / "opencode.json", setup)
    running = start_opencode(agent_dir, free_port(), secrets.token_urlsafe(16))
    try:
        wait_until_healthy(running)
        yield running
    finally:
        running.stop()


@dataclass
class AgentAPI:
    """The real API on a port, with opencode behind it and a scripted remote model."""

    http: httpx.AsyncClient
    model: ScriptedModel
    electron: StandInForElectron
    opencode_url: str
    password: str
    workspace_id: int

    def opencode(self) -> OpencodeClient:
        """A client for the opencode the API drives, to look behind the API."""
        return OpencodeClient(self.opencode_url, self.password)


@pytest_asyncio.fixture(loop_scope="function")
async def agent_api(
    base_url: str, scripted_model: ScriptedModel, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AgentAPI]:
    """Every part of an agent turn but Electron, which a stand-in plays."""
    needs_staged_opencode()
    # opencode's provider points at this API's model endpoint, on its real port.
    monkeypatch.setattr(get_settings(), "port", int(base_url.rsplit(":", 1)[1]))
    port, password = free_port(), secrets.token_urlsafe(16)
    opencode_url = f"http://127.0.0.1:{port}"
    monkeypatch.setattr(get_agent_settings(), "opencode_url", opencode_url)
    monkeypatch.setattr(get_agent_settings(), "opencode_password", password)
    monkeypatch.setattr(get_agent_settings(), "agent_untested_models", True)

    with create_session_factory(
        create_db_engine(get_storage_settings().database_path)
    )() as session:
        connection = ProviderConnection(
            label="Remote",
            provider="openai_compatible",
            base_url=f"{scripted_model.url}/v1",
            catalog_provider="openai",
        )
        connection.api_key = "remote-key"
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name=AGENT_MODEL,
            )
        )
        session.commit()

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as http:
        workspace = await http.post("/workspaces", json={"name": "Research"})
        workspace.raise_for_status()
        with StandInForElectron(
            get_storage_settings().agent_dir, port, password
        ) as electron:
            yield AgentAPI(
                http,
                scripted_model,
                electron,
                opencode_url,
                password,
                workspace.json()["id"],
            )


@pytest_asyncio.fixture(loop_scope="function")
async def tools(engine: Engine) -> AsyncIterator[ToolEndpoint]:
    """A fresh app on this test's database, its tool endpoint driven in-process."""
    async with endpoint_over(engine) as endpoint:
        yield endpoint


def declare_image_input(reads_images: bool) -> None:
    """The configuration the API writes for opencode, for a model that reads images or not."""
    setup = AgentSetup(
        model=MODEL,
        window=32768,
        reads_images=reads_images,
        endpoint_url="http://127.0.0.1:9/v1",
        launch_key="launch-key",
        route="chat_completions",
    )
    write_opencode_config(get_storage_settings().agent_dir / "opencode.json", setup)


@pytest.fixture
def model_reads_images() -> None:
    """opencode configured for a model that reads images, which page previews are for."""
    declare_image_input(True)


@pytest.fixture
def studio_worker() -> Iterator[None]:
    """The worker's Studio consumer, on a thread: a render runs its script while the tool waits."""
    stopping = threading.Event()

    def consume() -> None:
        while not stopping.is_set():
            task = studio_queue.dequeue()
            if task is None:
                stopping.wait(0.05)
            else:
                studio_queue.execute(task)

    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    yield
    stopping.set()
    thread.join(timeout=30)


@dataclass
class Endpoint:
    """The app as opencode reaches it, with the key it was launched with."""

    client: AsyncClient
    launch_key: str
    sessions: sessionmaker[Session]
    admission: LocalAdmission

    async def chat(self, body: dict, key: str | None = None) -> tuple[int, str]:
        """Send one request as opencode's provider does; the reply's status and text."""
        headers = {"Authorization": f"Bearer {self.launch_key if key is None else key}"}
        reply = await self.client.post(
            "/agent/model/v1/chat/completions", json=body, headers=headers
        )
        return reply.status_code, reply.text


@pytest.fixture
async def endpoint(engine: Engine) -> AsyncIterator[Endpoint]:
    """A fresh app on this test's database, driven in-process."""
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield Endpoint(
            client,
            app.state.agent_launch_key,
            app.state.session_factory,
            app.state.local_admission,
        )


def select_remote(sessions: sessionmaker[Session], base_url: str, api_key: str) -> None:
    """Choose a model behind a remote OpenAI-compatible connection."""
    with sessions() as session:
        connection = ProviderConnection(
            label="Remote", provider="openai_compatible", base_url=base_url
        )
        connection.api_key = api_key
        session.add(connection)
        session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                connection_id=connection.id,
                name="remote-model",
            )
        )
        session.commit()
