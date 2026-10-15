"""The API as a recording's ingest job reaches it: the transcription status, the
windows route, and the change notices it posts. Each test scripts the answers."""

import io
import json
import threading
import wave
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

MODEL = "nemotron-3.5-asr-streaming-0.6b-q8_0"


@dataclass
class SentWindow:
    seconds: float
    rate: int
    channels: int
    last: bool


@dataclass
class SpeechApi:
    status: dict = field(
        default_factory=lambda: {
            "ready": True,
            "reason": None,
            "model": MODEL,
            "language_intent": "auto",
            "languages": ["en", "es", "ja"],
        }
    )
    # Status and body for each window asked, in order; past them, `written`.
    replies: list[tuple[int, dict]] = field(default_factory=list)
    language: str | None = "en"
    windows: list[SentWindow] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    # Runs as window n is being answered, as a person's click lands meanwhile.
    during_window: Callable[[int], None] | None = None

    def written(self, n: int) -> dict:
        return {
            "text": f"Words of window {n}.",
            "language": self.language,
            "model_id": MODEL,
        }

    @staticmethod
    def waiting(reason: str, message: str = "Waiting") -> tuple[int, dict]:
        return 503, {
            "detail": {"code": "waiting", "reason": reason, "message": message}
        }

    @staticmethod
    def refused(status: int, code: str) -> tuple[int, dict]:
        return status, {"detail": {"code": code, "message": code}}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        api: SpeechApi = self.server.stand_in  # type: ignore[attr-defined]
        if self.path == "/llm/transcription/status":
            self._json(200, api.status)
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        api: SpeechApi = self.server.stand_in  # type: ignore[attr-defined]
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/internal/events":
            api.events.append(json.loads(body))
            self._json(202, {})
        elif self.path == "/internal/transcription/windows":
            n = len(api.windows)
            api.windows.append(_window(self.headers["Content-Type"], body))
            if api.during_window is not None:
                api.during_window(n)
            if n < len(api.replies):
                self._json(*api.replies[n])
            else:
                self._json(200, api.written(n))
        else:
            self.send_error(404)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def _window(content_type: str, body: bytes) -> SentWindow:
    boundary = content_type.split("boundary=")[1].encode()
    last = False
    clip = (0.0, 0, 0)
    for part in body.split(b"--" + boundary)[1:-1]:
        head, _, value = part.partition(b"\r\n\r\n")
        value = value.removesuffix(b"\r\n")
        if b"filename=" in head:
            with wave.open(io.BytesIO(value)) as audio:
                clip = (
                    audio.getnframes() / audio.getframerate(),
                    audio.getframerate(),
                    audio.getnchannels(),
                )
        elif b'name="last"' in head:
            last = value == b"true"
    return SentWindow(*clip, last=last)


@pytest.fixture
def speech_api(monkeypatch: pytest.MonkeyPatch) -> Iterator[SpeechApi]:
    """A stand-in on a real port, which the worker is pointed at as Electron does."""
    stand_in = SpeechApi()
    http = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    http.stand_in = stand_in  # type: ignore[attr-defined]
    threading.Thread(target=http.serve_forever, daemon=True).start()
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", str(http.server_port))
    yield stand_in
    http.shutdown()
    http.server_close()
