"""A plugin's `lifespan`: held open while the host serves, never in the way of startup."""

import contextlib
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

from host import app
from host.app import host_app
from host.tests.events import EVENTS
from host.tests.mcp_calls import raw_request, tool_names
from host.tests.serving import serving

PLUGINS = Path(__file__).parent / "shared_layer_plugins"


@pytest.fixture(autouse=True)
def events() -> Iterator[None]:
    EVENTS.clear()
    yield
    EVENTS.clear()


def happened(event: str, seconds: float = 5) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if event in EVENTS:
            return
        time.sleep(0.02)
    raise AssertionError(f"{event} did not happen: {EVENTS}")


def test_lifespans_are_held_while_serving_and_left_last_mounted_first() -> None:
    with serving(host_app(PLUGINS, {"first", "second"})) as base:
        happened("first entered")
        happened("second entered")
        assert httpx2.get(f"{base}/health").status_code == 200
        assert not [event for event in EVENTS if event.endswith("left")]

    assert EVENTS[-2:] == ["second left", "first left"]


async def test_lifespans_can_be_turned_off() -> None:
    """PLUGIN_LIFESPANS=off: a warm-up gone wrong is stopped without a release."""
    with serving(host_app(PLUGINS, {"first"}, lifespans=False)) as base:
        assert await tool_names(f"{base}/first/mcp") == ["wait"]

    assert EVENTS == []


def test_a_plugin_s_pools_close_after_its_calls_have_ended() -> None:
    """Calls end with the MCP servers, before the pools they use are closed."""
    call = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "wait", "arguments": {}},
    }
    with serving(host_app(PLUGINS, {"first"})) as base:
        threading.Thread(
            target=_sent, args=(f"{base}/first/mcp", call), daemon=True
        ).start()
        happened("call started")

    assert EVENTS.index("call ended") < EVENTS.index("first left")


async def test_a_failing_lifespan_leaves_the_host_serving(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with serving(host_app(PLUGINS, {"broken", "second"})) as base:
        happened("second entered")
        assert httpx2.get(f"{base}/health").status_code == 200
        assert await tool_names(f"{base}/broken/mcp") == ["search"]
        assert await tool_names(f"{base}/second/mcp") == ["search"]

    assert "broken: its lifespan failed" in caplog.text
    assert "the warm-up failed" in caplog.text
    assert "second left" in EVENTS


async def test_a_warm_up_that_never_ends_delays_neither_startup_nor_shutdown() -> None:
    began = time.monotonic()
    with serving(host_app(PLUGINS, {"stuck"})) as base:
        assert httpx2.get(f"{base}/health").status_code == 200
        assert await tool_names(f"{base}/stuck/mcp") == ["search"]
        happened("stuck warming")

    assert time.monotonic() - began < 5


def test_a_close_that_never_ends_is_cut_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The plugins mounted before it still close."""
    monkeypatch.setattr(app, "CLOSE_SECONDS", 0.2)
    with serving(host_app(PLUGINS, {"first", "lingering"})):
        happened("first entered")
        happened("lingering entered")
        began = time.monotonic()

    assert EVENTS[-2:] == ["lingering closing", "first left"]
    assert time.monotonic() - began < 3


def _sent(url: str, call: dict) -> None:
    """The call's answer does not matter: the host stops under it."""
    with contextlib.suppress(httpx2.HTTPError):
        raw_request(url, call)
