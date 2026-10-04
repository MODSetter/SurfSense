"""The recording proxy live runs put between SurfSense and Anthropic, driven against a stand-in."""

import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from tests.live.recording_proxy import RecordingProxy
from tests.live.spend_ledger import SpendLedger, Usage

pytestmark = pytest.mark.unit

KEY = "sk-test-not-a-real-key"
USAGE = {
    "prompt_tokens": 1200,
    "completion_tokens": 40,
    "prompt_tokens_details": {"cached_tokens": 200},
}


@dataclass
class Upstream:
    """Anthropic's OpenAI-compatible API, as far as the proxy can tell."""

    url: str = ""
    headers: list[dict[str, str]] = field(default_factory=list)
    bodies: list[dict] = field(default_factory=list)


class _Answers(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        upstream: Upstream = self.server.upstream  # type: ignore[attr-defined]
        upstream.headers.append(dict(self.headers))
        upstream.bodies.append(
            json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        )
        chunks = [
            {
                "choices": [
                    {"index": 0, "delta": {"role": "assistant", "content": "Hi"}}
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "call_1",
                                    "function": {"name": "read", "arguments": '{"a"'},
                                }
                            ]
                        },
                    }
                ]
            },
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "tool_calls": [
                                {"index": 0, "function": {"arguments": ":1}"}}
                            ]
                        },
                    }
                ]
            },
            {"choices": [], "usage": USAGE},
        ]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


class _BreaksMidStream(BaseHTTPRequestHandler):
    """Starts a reply it never finishes, as a reset connection leaves one."""

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers["Content-Length"]))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", "100000")
        self.end_headers()
        delta = {"choices": [{"index": 0, "delta": {"content": "Hi"}}]}
        self.wfile.write(f"data: {json.dumps(delta)}\n\n".encode())
        self.wfile.flush()
        self.close_connection = True

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def _serve(handler: type[BaseHTTPRequestHandler]) -> Iterator[Upstream]:
    """A stand-in for Anthropic on a loopback port."""
    stand_in = Upstream()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    server.upstream = stand_in  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stand_in.url = f"http://127.0.0.1:{server.server_port}/v1"
    yield stand_in
    server.shutdown()
    server.server_close()


@pytest.fixture
def upstream() -> Iterator[Upstream]:
    """Anthropic answering in full, its usage last."""
    yield from _serve(_Answers)


@pytest.fixture
def breaking_upstream() -> Iterator[Upstream]:
    """Anthropic's connection reset partway through a reply."""
    yield from _serve(_BreaksMidStream)


@pytest.fixture
def ledger(tmp_path: Path) -> SpendLedger:
    """A ledger of this test's own, never the real one."""
    return SpendLedger(tmp_path / "spend.json")


def _chat(proxy: RecordingProxy, **extra: object) -> httpx.Response:
    """A streamed chat request, as SurfSense's model endpoint relays one."""
    return httpx.post(
        f"{proxy.url}/chat/completions",
        json={
            "model": "claude-sonnet-5-5",
            "stream": True,
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": "Hello"}],
            **extra,
        },
        headers={"Authorization": "Bearer the-connections-placeholder"},
    )


def test_a_reply_streams_through_and_its_usage_is_charged(
    upstream: Upstream, ledger: SpendLedger
) -> None:
    """SurfSense gets the stream as sent; cached prompt tokens are charged at their own rate."""
    with RecordingProxy(upstream.url, KEY, ledger, case="smoke") as proxy:
        reply = _chat(proxy)

    assert reply.status_code == 200
    assert reply.text.endswith("data: [DONE]\n\n")
    spent = Usage(input_tokens=1000, output_tokens=40, cache_read_tokens=200)
    assert proxy.usage() == spent
    assert ledger.total() == spent
    (exchange,) = proxy.exchanges
    assert exchange.reply_text == "Hi"
    assert exchange.tool_calls == [{"name": "read", "arguments": '{"a":1}'}]
    assert exchange.request["messages"] == [{"role": "user", "content": "Hello"}]


def test_the_key_goes_upstream_in_place_of_the_placeholder_and_is_never_recorded(
    upstream: Upstream, ledger: SpendLedger
) -> None:
    """The key stays in memory: not in the transcript, not in the ledger."""
    with RecordingProxy(upstream.url, KEY, ledger, case="smoke") as proxy:
        _chat(proxy)

    (headers,) = upstream.headers
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert KEY not in json.dumps(proxy.transcript())
    assert KEY not in ledger.path.read_text(encoding="utf-8")


def test_usage_is_asked_for_on_every_streamed_request(
    upstream: Upstream, ledger: SpendLedger
) -> None:
    """Without it a streamed reply carries no usage, and spend could not be exact."""
    with RecordingProxy(upstream.url, KEY, ledger, case="smoke") as proxy:
        _chat(proxy)

    assert upstream.bodies[0]["stream_options"] == {"include_usage": True}


def test_a_request_that_could_reach_the_stop_never_leaves(
    upstream: Upstream, tmp_path: Path
) -> None:
    """The stop holds inside a run too, before a call is paid for."""
    ledger = SpendLedger(tmp_path / "spend.json", stop_dollars=1.0)
    ledger.add(Usage(input_tokens=499_000), case="earlier")  # $0.998

    with RecordingProxy(upstream.url, KEY, ledger, case="smoke") as proxy:
        reply = _chat(proxy)

    assert reply.status_code == 400
    assert "budget" in reply.json()["error"]["message"]
    assert upstream.bodies == []
    assert proxy.refused is True


def test_images_a_request_carries_are_counted_and_kept_out_of_the_transcript(
    upstream: Upstream, ledger: SpendLedger
) -> None:
    """Whether a page image reached the model is the question; its bytes are not."""
    image = "data:image/png;base64," + "A" * 4000
    with RecordingProxy(upstream.url, KEY, ledger, case="images") as proxy:
        httpx.post(
            f"{proxy.url}/chat/completions",
            json={
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Look"},
                            {"type": "image_url", "image_url": {"url": image}},
                        ],
                    }
                ],
            },
        )

    (exchange,) = proxy.exchanges
    assert exchange.images == [{"message": 0, "role": "user", "mime": "image/png"}]
    assert "A" * 4000 not in json.dumps(proxy.transcript())


def test_a_reply_cut_off_before_its_usage_is_charged_at_the_worst_case(
    breaking_upstream: Upstream, ledger: SpendLedger
) -> None:
    """Anthropic bills what it read and wrote before the break; $0 would let the stop come late."""
    with RecordingProxy(breaking_upstream.url, KEY, ledger, case="demo") as proxy:
        _chat(proxy)

    (exchange,) = proxy.exchanges
    assert exchange.error is not None
    assert exchange.usage_estimated is True
    assert exchange.usage.output_tokens == 1000  # the request's max_tokens
    assert exchange.usage.dollars > 0
    assert ledger.total() == exchange.usage
    (recorded,) = proxy.transcript()
    assert recorded["usage_estimated"] is True


def test_a_reply_with_its_usage_is_charged_as_reported(
    upstream: Upstream, ledger: SpendLedger
) -> None:
    """Only a reply that never said what it used is estimated."""
    with RecordingProxy(upstream.url, KEY, ledger, case="smoke") as proxy:
        _chat(proxy)

    (recorded,) = proxy.transcript()
    assert recorded["usage_estimated"] is False
