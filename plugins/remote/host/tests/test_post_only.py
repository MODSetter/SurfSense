"""Each plugin's endpoint takes POST only: a GET would hold an idle event stream open."""

from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

from host.app import host_app
from host.tests.events import EVENTS
from host.tests.mcp_calls import HANDSHAKE_HEADERS, tool_names
from host.tests.serving import serving

SAMPLES = Path(__file__).parent / "sample_plugins"
PLUGINS = Path(__file__).parent / "shared_layer_plugins"


@pytest.fixture(autouse=True)
def events() -> Iterator[None]:
    EVENTS.clear()
    yield
    EVENTS.clear()


@pytest.mark.parametrize("method", ["GET", "DELETE"])
def test_get_and_delete_are_not_allowed(method: str) -> None:
    """opencode's client reads 405 as a server that offers no stream of its own."""
    with serving(host_app(SAMPLES)) as base:
        answer = httpx2.request(method, f"{base}/notes/mcp", headers=HANDSHAKE_HEADERS)

    assert answer.status_code == 405
    assert answer.headers["allow"] == "POST"
    assert answer.json()["error"]["message"] == "Method Not Allowed"


async def test_post_is_answered_as_before() -> None:
    with serving(host_app(SAMPLES)) as base:
        assert await tool_names(f"{base}/notes/mcp") == ["search"]


def test_a_refused_get_costs_no_license_check() -> None:
    with serving(host_app(PLUGINS, {"guarded"})) as base:
        assert httpx2.get(f"{base}/guarded/mcp").status_code == 405
        assert EVENTS == []
        assert httpx2.post(f"{base}/guarded/mcp", json={}).status_code == 401

    assert EVENTS == ["guard asked"]


def test_another_path_is_still_not_found() -> None:
    with serving(host_app(SAMPLES)) as base:
        assert httpx2.get(f"{base}/notes/other").status_code == 404
