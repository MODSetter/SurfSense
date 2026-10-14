"""audio.cpp's transcription server as the API reaches it: the model it lists,
whether it is loaded, what each request carried, and what it unloaded."""

import io
import json
import threading
import wave
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from shared.config import get_llm_settings

MODEL = "nemotron-3.5-asr-streaming-0.6b-q8_0"


@dataclass
class TranscriptionServer:
    url: str = ""
    models: list[str] = field(default_factory=lambda: [MODEL])
    loaded: bool = False
    # What every transcription answers, tags and all.
    text: str = ""
    # Each request's fields, and its audio's length as `seconds`.
    requests: list[dict] = field(default_factory=list)
    unloaded: list[str] = field(default_factory=list)
    # Statuses to answer the next transcriptions with, one each.
    failures: list[int] = field(default_factory=list)
    # Set while a transcription is held open; it answers once released.
    running: threading.Event = field(default_factory=threading.Event)
    release: threading.Event | None = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        server: TranscriptionServer = self.server.stand_in  # type: ignore[attr-defined]
        if self.path == "/v1/models":
            self._json(
                200,
                {
                    "object": "list",
                    "data": [
                        {"id": m, "task": "asr", "loaded": server.loaded}
                        for m in server.models
                    ],
                },
            )
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        server: TranscriptionServer = self.server.stand_in  # type: ignore[attr-defined]
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/v1/tasks/unload_models":
            ids = json.loads(body)["model_ids"]
            server.unloaded.extend(ids)
            server.loaded = False
            self._json(200, {"unloaded": ids, "not_found": []})
        elif self.path == "/v1/audio/transcriptions/details":
            fields = _form(self.headers["Content-Type"], body)
            server.requests.append(fields)
            if server.failures:
                status = server.failures.pop(0)
                self._json(status, {"error": {"message": f"failed with {status}"}})
                return
            server.running.set()
            if server.release is not None:
                server.release.wait(timeout=10)
            server.loaded = True
            self._json(200, {"text": server.text})
        else:
            self.send_error(404)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def _form(content_type: str, body: bytes) -> dict:
    boundary = content_type.split("boundary=")[1].encode()
    fields: dict = {}
    for part in body.split(b"--" + boundary)[1:-1]:
        head, _, value = part.partition(b"\r\n\r\n")
        value = value.removesuffix(b"\r\n")
        name = head.split(b'name="')[1].split(b'"')[0].decode()
        if b"filename=" in head:
            with wave.open(io.BytesIO(value)) as clip:
                fields["seconds"] = clip.getnframes() / clip.getframerate()
        else:
            fields[name] = value.decode()
    return fields


@pytest.fixture
def transcription_server(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TranscriptionServer]:
    """A stand-in on a real port, which the API is told about as Electron would."""
    stand_in = TranscriptionServer()
    http = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    http.stand_in = stand_in  # type: ignore[attr-defined]
    threading.Thread(target=http.serve_forever, daemon=True).start()
    stand_in.url = f"http://127.0.0.1:{http.server_port}"
    monkeypatch.setattr(get_llm_settings(), "transcription_base_url", stand_in.url)
    monkeypatch.setattr(
        "modules.llm.providers.audiocpp.transcription.RETRY_AFTER_SECONDS", 0.01
    )
    yield stand_in
    if stand_in.release is not None:
        stand_in.release.set()
    http.shutdown()
    http.server_close()
