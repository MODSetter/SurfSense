import contextlib
import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import uvicorn
from sqlalchemy import Engine

from api.main import create_app
from shared.config import get_llm_settings
from shared.db import create_session_factory

# The reply the stub streams back, split so the route emits more than one delta.
REPLY_DELTAS = ["Revenue ", "climbed after the launch [1]."]

# Each chat request the stub received, so a test can assert what the route sent.
_REQUESTS: list[dict] = []

# The context window /props reports, or None to omit it (an older build /
# a model report a test does not care about). Set per test before the fixture
# starts the server.
_PROPS_N_CTX: int | None = None

# The slots /props reports, or None to omit it, as a stub that does not care.
_PROPS_SLOTS: int | None = None

# Tokens per word /tokenize reports, or None to answer 404 (an older build).
# Set per test before the fixture starts the server.
_TOKENS_PER_WORD: int | None = None

# The trace a thinking model streams as `reasoning_content` before its answer,
# as llama-server does under `--reasoning-format deepseek`. Empty: no thinking.
_REASONING: list[str] = []

# The `prompt_progress` objects the stub sends before anything else, when asked.
_PROMPT_PROGRESS: list[dict] = []

# Whether the stub's model has a projector that reads images, which the real
# router lists as `image` input on `/models`.
_SEES = False

# The answer the stub streams, or None for REPLY_DELTAS. Empty: a model that
# closes its stream without writing anything.
_ANSWER: list[str] | None = None

# Set, the stub sends its answer and then holds the stream open until the event
# fires, as a model still generating does. None: it answers straight through.
_STALL: threading.Event | None = None


class StubRouterChat(BaseHTTPRequestHandler):
    """The router's OpenAI chat endpoint, streaming its reply as SSE.

    The local runtime speaks OpenAI now, so the adapter composes the same
    provider a remote endpoint uses and this stub is shaped accordingly.
    """

    def do_GET(self) -> None:
        if self.path == "/models":
            self._send(
                json.dumps(
                    {
                        "object": "list",
                        "data": [
                            {
                                "id": name,
                                "architecture": {
                                    "input_modalities": ["text", "image"]
                                    if _SEES
                                    else ["text"]
                                },
                                "status": {"value": "loaded"},
                            }
                            for name in ("Qwen3-4B-Q4_K_M", "Qwen3-1.7B-Q4_K_M")
                        ],
                    }
                ).encode()
            )
        elif self.path.startswith("/props"):
            settings = (
                {"n_ctx": _PROPS_N_CTX} if _PROPS_N_CTX is not None else {}
            )
            props: dict = {"default_generation_settings": settings}
            if _PROPS_SLOTS is not None:
                props["total_slots"] = _PROPS_SLOTS
            self._send(json.dumps(props).encode())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path not in ("/v1/chat/completions", "/models/load", "/tokenize"):
            self.send_error(404)
            return
        if self.path == "/models/load":
            self._send(b'{"success": true}')
            return
        if self.path == "/tokenize":
            if _TOKENS_PER_WORD is None:
                self.send_error(404)
                return
            words = json.loads(raw).get("content", "").split()
            self._send(
                json.dumps({"tokens": list(range(len(words) * _TOKENS_PER_WORD))}).encode()
            )
            return

        request = json.loads(raw)
        _REQUESTS.append(request)
        deltas = (
            ["Revenue ", "Growth"]
            if request.get("max_tokens") == 12
            else REPLY_DELTAS
            if _ANSWER is None
            else _ANSWER
        )
        # The real server thinks unless the request carries its off switch.
        thinking_off = request.get("thinking_budget_tokens") == 0
        trace = [] if request.get("max_tokens") == 12 or thinking_off else _REASONING
        # The real server reports progress only where the request asks for it.
        progress = _PROMPT_PROGRESS if request.get("return_progress") else []
        chunks = (
            [
                "data: "
                + json.dumps(
                    {
                        "choices": [{"delta": {"role": "assistant", "content": None}}],
                        "prompt_progress": reported,
                    }
                )
                for reported in progress
            ]
            + [
                "data: "
                + json.dumps({"choices": [{"delta": {"reasoning_content": piece}}]})
                for piece in trace
            ]
            + [
                "data: " + json.dumps({"choices": [{"delta": {"content": delta}}]})
                for delta in deltas
            ]
            + ["data: [DONE]"]
        )
        if _STALL is not None and request.get("max_tokens") != 12:
            self._stream_until_released(chunks[:-1], chunks[-1], _STALL)
            return
        self._send(("\n\n".join(chunks) + "\n\n").encode())

    def _stream_until_released(
        self, chunks: list[str], last: str, release: threading.Event
    ) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(f"{chunk}\n\n".encode())
            self.wfile.flush()
        release.wait(timeout=10)
        # The route may already have hung up, which is what the test is for.
        with contextlib.suppress(OSError):
            self.wfile.write(f"{last}\n\n".encode())

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def llamacpp_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict]]:
    """A real llama-server stand-in on a real port; yields the requests it sees."""
    global _PROPS_N_CTX, _PROPS_SLOTS, _TOKENS_PER_WORD, _SEES, _ANSWER, _STALL
    _REQUESTS.clear()
    _PROPS_SLOTS = None
    _SEES = False
    _REASONING.clear()
    _PROMPT_PROGRESS.clear()
    _ANSWER = None
    _STALL = None
    _PROPS_N_CTX = None
    _TOKENS_PER_WORD = None
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRouterChat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", url)

    yield _REQUESTS

    if _STALL is not None:
        _STALL.set()
    server.shutdown()
    server.server_close()


class StubRouterUnauthorized(BaseHTTPRequestHandler):
    """A router that always answers 401, as if the connection were bad.

    It still answers `GET /models`, because the adapter checks residency before
    it asks a question and a 501 there would fail the request for the wrong
    reason entirely.
    """

    def do_GET(self) -> None:
        body = b'{"object": "list", "data": []}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        body = b'{"error": "unauthorized"}'
        self.send_response(401)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def set_props_n_ctx(n_ctx: int) -> None:
    """Make the next `llamacpp_server` request report this context window."""
    global _PROPS_N_CTX
    _PROPS_N_CTX = n_ctx


def set_props_slots(slots: int) -> None:
    """Make the next `llamacpp_server` report this many slots, as `--parallel` sets."""
    global _PROPS_SLOTS
    _PROPS_SLOTS = slots


def set_tokens_per_word(tokens_per_word: int) -> None:
    """Make the next `llamacpp_server` request answer `/tokenize` exactly,
    at this many tokens per word, instead of 404ing like an older build."""
    global _TOKENS_PER_WORD
    _TOKENS_PER_WORD = tokens_per_word


def set_sees(sees: bool) -> None:
    """Make the `llamacpp_server` model read images, as a vision model's does."""
    global _SEES
    _SEES = sees


def set_reasoning(pieces: list[str]) -> None:
    """Make the `llamacpp_server` answer think out loud before it replies."""
    _REASONING[:] = pieces


def set_prompt_progress(reported: list[dict]) -> None:
    """Make the `llamacpp_server` report reading the prompt before it replies."""
    _PROMPT_PROGRESS[:] = reported


def set_answer(pieces: list[str]) -> None:
    """Make the `llamacpp_server` answer with these deltas instead of the default."""
    global _ANSWER
    _ANSWER = pieces


def stall_after_answer() -> threading.Event:
    """Make the `llamacpp_server` hold its stream open after the answer; set to end it."""
    global _STALL
    _STALL = threading.Event()
    return _STALL


@pytest.fixture
def live_url(engine: Engine) -> Iterator[str]:
    """The app behind a real uvicorn socket, so a client can hang up mid-stream.

    The in-process transport buffers a response to its end and never reports a
    disconnect, which is the one path this has to reach.
    """
    app = create_app()
    app.state.session_factory = create_session_factory(engine)
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)

    yield f"http://127.0.0.1:{server.servers[0].sockets[0].getsockname()[1]}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def llamacpp_server_unauthorized(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A chat stand-in that fails every request, for exercising error handling."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRouterUnauthorized)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_llm_settings(), "llamacpp_base_url", url)

    yield

    server.shutdown()
    server.server_close()


class RemoteEndpoint:
    """A remote OpenAI-compatible host, as a connection reaches it.

    `status` answers every chat request with that error instead; `stall`, set,
    holds each reply open after its answer until the event fires, as a model
    still generating does. `open_streams` counts replies being written right
    now, so a test can see two run at once.
    """

    def __init__(self) -> None:
        self.status: int | None = None
        self.stall: threading.Event | None = None
        self.open_streams = 0
        self.most_open = 0
        self.lock = threading.Lock()


_REMOTE = RemoteEndpoint()


class StubRemoteChat(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._send(b'{"object": "list", "data": [{"id": "remote-model"}]}')

    def do_POST(self) -> None:
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        # A thread's title is a short request of its own; only the reply stalls.
        titling = request.get("max_tokens") == 12
        if _REMOTE.status is not None:
            body = b'{"error": {"message": "slow down"}}'
            self.send_response(_REMOTE.status)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        with _REMOTE.lock:
            _REMOTE.open_streams += 0 if titling else 1
            _REMOTE.most_open = max(_REMOTE.most_open, _REMOTE.open_streams)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for delta in REPLY_DELTAS:
                chunk = json.dumps({"choices": [{"delta": {"content": delta}}]})
                self.wfile.write(f"data: {chunk}\n\n".encode())
                self.wfile.flush()
            if _REMOTE.stall is not None and not titling:
                _REMOTE.stall.wait(timeout=10)
            with contextlib.suppress(OSError):
                self.wfile.write(b"data: [DONE]\n\n")
        finally:
            with _REMOTE.lock:
                _REMOTE.open_streams -= 0 if titling else 1

    def _send(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


@pytest.fixture
def remote_endpoint(engine: Engine) -> Iterator[RemoteEndpoint]:
    """A remote connection on a real port, selected as the chat model.

    Loopback is not egress, so no host has to be allowed first.
    """
    global _REMOTE
    _REMOTE = RemoteEndpoint()
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRemoteChat)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    from modules.llm.model_type import ModelType
    from modules.llm.models import ProviderConnection, SelectedModel

    with create_session_factory(engine)() as session:
        connection = ProviderConnection(
            label="Remote",
            provider="openai_compatible",
            base_url=f"http://127.0.0.1:{server.server_port}",
        )
        session.add(connection)
        session.flush()
        selected = session.get(SelectedModel, ModelType.TEXT_GEN)
        if selected is not None:
            session.delete(selected)
            session.flush()
        session.add(
            SelectedModel(
                model_type=ModelType.TEXT_GEN,
                provider="openai_compatible",
                name="remote-model",
                connection_id=connection.id,
            )
        )
        session.commit()

    yield _REMOTE

    if _REMOTE.stall is not None:
        _REMOTE.stall.set()
    server.shutdown()
    server.server_close()
