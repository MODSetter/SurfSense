import pytest

from modules.egress import last_calls
from modules.egress.last_calls import LastCalls

pytestmark = pytest.mark.unit


def test_a_hosts_call_is_recorded_at_most_once_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings > Network shows a host's last call, with no write for each request."""
    calls = LastCalls()
    now = [1000.0]
    monkeypatch.setattr(last_calls.time, "monotonic", lambda: now[0])

    first = calls.due("plugins.example")
    again = calls.due("plugins.example")
    now[0] += last_calls.RECORD_SECONDS

    assert (first, again) == ("host:plugins.example", None)
    assert calls.due("plugins.example") == "host:plugins.example"
    assert calls.due("localhost") is None
