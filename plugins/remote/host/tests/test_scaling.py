import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

from host.app import host_app
from host.cancel_broadcast import RedisBroadcast
from host.tests.mcp_calls import raw_request, tool_names
from host.tests.redis_server import redis_url
from host.tests.serving import serving

SAMPLES = Path(__file__).parent / "sample_plugins"

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "opencode", "version": "1.18.34"},
    },
}


@pytest.fixture
def redis(tmp_path: Path) -> Iterator[str]:
    with redis_url(tmp_path) as url:
        yield url


class SlowCall:
    """A call left running, its connection open, as opencode leaves one it stopped."""

    def __init__(self, url: str, mark: Path, headers: dict[str, str]) -> None:
        self.answer: httpx2.Response | None = None
        self.failure: Exception | None = None
        call = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "wait", "arguments": {"mark": str(mark)}},
        }
        self._thread = threading.Thread(
            target=self._send, args=(url, call, headers), daemon=True
        )
        self._thread.start()
        wait_for(mark, "started")

    def _send(self, url: str, call: dict, headers: dict[str, str]) -> None:
        try:
            self.answer = raw_request(url, call, headers)
        except Exception as error:
            self.failure = error

    def ended(self) -> "SlowCall":
        self._thread.join(timeout=5)
        return self


def wait_for(mark: Path, state: str, seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if mark.exists() and mark.read_text() == state:
            return
        time.sleep(0.05)
    raise AssertionError(
        f"{mark.read_text() if mark.exists() else 'nothing'}, not {state}"
    )


def stop(base: str, headers: dict[str, str]) -> httpx2.Response:
    return httpx2.post(f"{base}/cancel", headers=headers)


THREAD = {"authorization": "License k-1", "x-surfsense-calls": "t-1"}


def test_any_copy_answers_a_request_another_copy_began() -> None:
    """No session is kept, so the load balancer may send each request anywhere."""
    with serving(host_app(SAMPLES)) as a, serving(host_app(SAMPLES)) as b:
        began = raw_request(f"{a}/notes/mcp", INITIALIZE)
        listed = raw_request(
            f"{b}/notes/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )

    assert began.headers.get("mcp-session-id") is None
    assert listed.status_code == 200
    assert '"search"' in listed.text


async def test_a_container_serves_only_the_plugins_it_is_given() -> None:
    """How a plugin is split into a container of its own, from the same image."""
    with serving(host_app(SAMPLES, plugins={"notes"})) as base:
        assert await tool_names(f"{base}/notes/mcp") == ["search"]
        assert httpx2.post(f"{base}/failing/mcp").status_code == 404


def test_a_plugin_not_found_stops_the_host() -> None:
    """A mistyped PLUGINS fails the deploy, not a user's first call."""
    with pytest.raises(ValueError, match="nope"):
        host_app(SAMPLES, plugins={"nope"})


def test_stop_cancels_the_thread_s_call(tmp_path: Path) -> None:
    mark = tmp_path / "mark"
    with serving(host_app(SAMPLES)) as base:
        call = SlowCall(f"{base}/slow/mcp", mark, THREAD)

        stopped = stop(base, THREAD)

        assert stopped.status_code == 202
        wait_for(mark, "cancelled")
        ended = call.ended()
    # Its response ends whole, saying it was cancelled, rather than cut off.
    assert ended.failure is None
    assert ended.answer is not None
    assert "Request cancelled" in ended.answer.text


@pytest.mark.parametrize(
    "other",
    [
        {"authorization": "License k-1", "x-surfsense-calls": "t-2"},
        {"authorization": "License k-2", "x-surfsense-calls": "t-1"},
    ],
)
def test_stop_from_another_thread_or_license_cancels_nothing(
    tmp_path: Path, other: dict[str, str]
) -> None:
    """The token and the license together name the calls a Stop may end."""
    mark = tmp_path / "mark"
    with serving(host_app(SAMPLES)) as base:
        call = SlowCall(f"{base}/slow/mcp", mark, THREAD)

        stop(base, other)
        time.sleep(0.5)

        assert mark.read_text() == "started"
        stop(base, THREAD)
        wait_for(mark, "cancelled")
        call.ended()


def test_stop_without_a_token_is_refused() -> None:
    with serving(host_app(SAMPLES)) as base:
        assert stop(base, {"authorization": "License k-1"}).status_code == 400


def test_stop_reaches_the_copy_running_the_call(tmp_path: Path, redis: str) -> None:
    """Sent to any copy, the Stop is passed on through Redis to the one with the call."""
    mark = tmp_path / "mark"
    first = host_app(SAMPLES, broadcast=RedisBroadcast(redis))
    second = host_app(SAMPLES, broadcast=RedisBroadcast(redis))
    with serving(first) as a, serving(second) as b:
        call = SlowCall(f"{a}/slow/mcp", mark, THREAD)

        assert stop(b, THREAD).status_code == 202

        wait_for(mark, "cancelled")
        call.ended()
