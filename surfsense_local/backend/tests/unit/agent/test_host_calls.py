"""A call a runtime gave up on, ended on SurfSense's plugin host, which never hears the cancel itself."""

import json

import pytest

from modules.agent.plugin_gateway import host_calls
from modules.agent.plugin_gateway.host_calls import HostCalls

pytestmark = pytest.mark.unit

HOST = ("https://plugins.surfsense.test", "Bearer a", "thread-7")


def _call(request_id: int) -> bytes:
    return json.dumps(
        {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {}}
    ).encode()


def _cancel(request_id: int) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": request_id, "reason": "Request timed out"},
        }
    ).encode()


@pytest.fixture
def stopped(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Each host told to end its calls, in order."""
    stops: list[tuple[str, ...]] = []
    monkeypatch.setattr(host_calls, "stop_soon", lambda key, headers: stops.append(key))
    return stops


def test_a_call_given_up_on_alone_is_ended_at_once(stopped: list) -> None:
    """Nothing else of the thread runs there, so its host is told at once."""
    calls = HostCalls()

    calls.sent(HOST, _call(1), {})
    calls.sent(HOST, _cancel(1), {})

    assert stopped == [HOST]


def test_one_still_working_is_not_cut_short(stopped: list) -> None:
    """The host ends all the thread's calls at once, so it waits for the others to finish."""
    calls = HostCalls()

    calls.sent(HOST, _call(1), {})
    calls.sent(HOST, _call(2), {})
    calls.sent(HOST, _cancel(1), {})
    waited = list(stopped)
    calls.answered(HOST, 2)

    assert waited == []
    assert stopped == [HOST]


def test_a_call_that_ended_needs_no_stop(stopped: list) -> None:
    """Its answer came; a late cancel has nothing to end."""
    calls = HostCalls()

    calls.sent(HOST, _call(1), {})
    calls.answered(HOST, 1)
    calls.sent(HOST, _cancel(1), {})

    assert stopped == []


def test_another_thread_s_calls_are_its_own(stopped: list) -> None:
    """Another thread's call on the same host never holds this one's stop back."""
    calls = HostCalls()
    other = (*HOST[:2], "thread-8")

    calls.sent(HOST, _call(1), {})
    calls.sent(other, _call(1), {})
    calls.sent(HOST, _cancel(1), {})

    assert stopped == [HOST]
