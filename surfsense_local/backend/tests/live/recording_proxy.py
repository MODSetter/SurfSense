"""A loopback proxy between SurfSense's model endpoint and Anthropic that records and charges each call.

The connection under test points here with a placeholder key; the real key lives
only in this process's memory and goes upstream in the headers SurfSense sends
to api.anthropic.com, so it never reaches SurfSense's database, opencode or a file.
"""

import base64
import copy
import json
import math
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from modules.llm.connections.key_headers import key_headers
from tests.live.spend_ledger import SpendLedger, Usage

ANTHROPIC = "https://api.anthropic.com/v1"
# Worst case before a call is sent: the live runs' JSON came to 2.8 to 2.9
# characters a token, and a request that names no output cap could ask for
# opencode's cap.
_CHARS_PER_TOKEN = 2
_DEFAULT_MAX_TOKENS = 32_000
# Anthropic reads an image as its pixels over 750, and only ever scales one down;
# its base64 runs to far more characters than that.
_PIXELS_PER_TOKEN = 750
_UPSTREAM_TIMEOUT = httpx.Timeout(600.0, connect=10.0)


@dataclass
class Exchange:
    """One chat request as it went upstream, and what came back."""

    request: dict[str, Any]
    status: int = 0
    reply_text: str = ""
    tool_calls: list[dict[str, str]] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    # No usage came back, so the call is charged at its worst case.
    usage_estimated: bool = False
    images: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class RecordingProxy:
    """Serves `<url>/chat/completions` on a free loopback port while open."""

    def __init__(
        self, upstream: str, api_key: str, ledger: SpendLedger, case: str
    ) -> None:
        self.upstream = upstream.rstrip("/")
        self.ledger = ledger
        self.case = case
        self.exchanges: list[Exchange] = []
        self.refused = False
        self._key = api_key
        self._lock = threading.Lock()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._server.proxy = self  # type: ignore[attr-defined]
        self.url = f"http://127.0.0.1:{self._server.server_port}/v1"

    def __enter__(self) -> "RecordingProxy":
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()

    def usage(self) -> Usage:
        """What this proxy's calls have used so far."""
        with self._lock:
            return sum((e.usage for e in self.exchanges), Usage())

    def transcript(self) -> list[dict[str, Any]]:
        """Every exchange, redacted: no key, and each image only as its type."""
        with self._lock:
            return [
                {
                    "request": _without_image_data(e.request),
                    "status": e.status,
                    "reply_text": e.reply_text,
                    "tool_calls": e.tool_calls,
                    "usage": e.usage.__dict__,
                    "usage_estimated": e.usage_estimated,
                    "images": e.images,
                    "error": e.error,
                }
                for e in self.exchanges
            ]

    def redact(self, text: str) -> str:
        return text.replace(self._key, "[REDACTED]") if self._key else text

    def forward(self, body: dict[str, Any], respond: "_Handler") -> None:
        """Send one chat request upstream, stream the reply back, and charge it."""
        exchange = Exchange(request=body, images=_images_in(body))
        worst_case = _worst_case_usage(body)
        if not self.ledger.has_room(worst_case.dollars):
            self.refused = True
            respond.error(
                400,
                f"live budget stop: ${self.ledger.total().dollars:.2f} spent of the "
                f"${self.ledger.stop_dollars:.0f} stop",
            )
            return
        if body.get("stream"):
            body = {**body, "stream_options": {"include_usage": True}}
        with self._lock:
            self.exchanges.append(exchange)
        headers = {"Content-Type": "application/json"}
        headers.update(key_headers(self.upstream, self._key))
        try:
            with httpx.stream(
                "POST",
                f"{self.upstream}/chat/completions",
                json=body,
                headers=headers,
                timeout=_UPSTREAM_TIMEOUT,
            ) as reply:
                exchange.status = reply.status_code
                respond.begin(reply.status_code, reply.headers.get("content-type"))
                if reply.status_code >= 400 or not body.get("stream"):
                    content = reply.read()
                    respond.write(content)
                    self._read_whole(exchange, content)
                else:
                    for line in reply.iter_lines():
                        respond.write(f"{line}\n".encode())
                        self._read_line(exchange, line)
        except httpx.HTTPError as failure:
            exchange.error = self.redact(f"{type(failure).__name__}: {failure}")
        finally:
            # A reply cut off before its last chunk is still billed for what Anthropic
            # read and wrote; an error answer is not.
            if exchange.usage == Usage() and exchange.status < 400:
                exchange.usage, exchange.usage_estimated = worst_case, True
            self.ledger.add(exchange.usage, self.case)

    def _read_whole(self, exchange: Exchange, content: bytes) -> None:
        text = self.redact(content.decode("utf-8", "replace"))
        try:
            reply = json.loads(text)
        except ValueError:
            exchange.error = text[:2000]
            return
        if exchange.status >= 400:
            exchange.error = text[:2000]
        message = ((reply.get("choices") or [{}])[0]).get("message") or {}
        exchange.reply_text = message.get("content") or ""
        exchange.tool_calls = [
            {"name": c["function"]["name"], "arguments": c["function"]["arguments"]}
            for c in message.get("tool_calls") or []
        ]
        exchange.usage = _usage(reply.get("usage"))

    def _read_line(self, exchange: Exchange, line: str) -> None:
        data = line.removeprefix("data:").strip()
        if not line.startswith("data:") or not data or data == "[DONE]":
            return
        chunk = json.loads(data)
        if chunk.get("error"):
            exchange.error = self.redact(json.dumps(chunk["error"]))[:2000]
        if chunk.get("usage"):
            exchange.usage = _usage(chunk["usage"])
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            exchange.reply_text += delta.get("content") or ""
            for call in delta.get("tool_calls") or []:
                while len(exchange.tool_calls) <= call.get("index", 0):
                    exchange.tool_calls.append({"name": "", "arguments": ""})
                made = exchange.tool_calls[call.get("index", 0)]
                function = call.get("function") or {}
                made["name"] += function.get("name") or ""
                made["arguments"] += function.get("arguments") or ""


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        proxy: RecordingProxy = self.server.proxy  # type: ignore[attr-defined]
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if not self.path.endswith("/chat/completions"):
            self.error(404, f"no route {self.path}")
            return
        proxy.forward(body, self)

    def begin(self, status: int, content_type: str | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/json")
        self.end_headers()

    def write(self, data: bytes) -> None:
        try:
            self.wfile.write(data)
            self.wfile.flush()
        except OSError:
            pass  # SurfSense hung up, which a stopped turn does

    def error(self, status: int, message: str) -> None:
        self.begin(status, "application/json")
        self.write(json.dumps({"error": {"message": message}}).encode())

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def _usage(reported: dict[str, Any] | None) -> Usage:
    """Anthropic's usage in OpenAI's shape; cached prompt tokens are billed apart."""
    if not reported:
        return Usage()
    cached = (reported.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    written = reported.get("cache_creation_input_tokens") or 0
    prompt = reported.get("prompt_tokens") or 0
    return Usage(
        input_tokens=max(prompt - cached - written, 0),
        output_tokens=reported.get("completion_tokens") or 0,
        cache_read_tokens=cached,
        cache_write_tokens=written,
    )


def _worst_case_usage(body: dict[str, Any]) -> Usage:
    """The prompt at the dearest input rate, and the whole output cap.

    An image whose size cannot be read is counted as text, which is dearer.
    """
    text_chars = len(json.dumps(body))
    image_tokens = 0
    for _, _, url in _image_parts(body):
        pixels = _pixels(url)
        if pixels is not None:
            text_chars -= len(url)
            image_tokens += math.ceil(pixels / _PIXELS_PER_TOKEN)
    return Usage(
        cache_write_tokens=math.ceil(text_chars / _CHARS_PER_TOKEN) + image_tokens,
        output_tokens=body.get("max_tokens") or _DEFAULT_MAX_TOKENS,
    )


def _pixels(url: str) -> int | None:
    """An inline image's width times height, read from its header; None if it has none."""
    head, _, data = url.partition(";base64,")
    if not head.startswith("data:image/") or not data:
        return None
    try:
        with Image.open(BytesIO(base64.b64decode(data))) as image:
            width, height = image.size
    except (ValueError, OSError, Image.DecompressionBombError):
        return None
    return width * height


def _images_in(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Each image part the request carries: which message, whose, and what kind."""
    return [
        {
            "message": index,
            "role": role,
            "mime": url.split(";", 1)[0].removeprefix("data:"),
        }
        for index, role, url in _image_parts(body)
    ]


def _image_parts(body: dict[str, Any]) -> list[tuple[int, str | None, str]]:
    """Each image part's message index, that message's role, and its URL."""
    found = []
    for index, message in enumerate(body.get("messages") or []):
        content = message.get("content")
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                found.append((index, message.get("role"), url))
    return found


def _without_image_data(request: dict[str, Any]) -> dict[str, Any]:
    kept = copy.deepcopy(request)
    for message in kept.get("messages") or []:
        content = message.get("content")
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and part.get("type") == "image_url":
                url = part["image_url"].get("url", "")
                part["image_url"]["url"] = f"{url.split(',', 1)[0]},<{len(url)} chars>"
    return kept
