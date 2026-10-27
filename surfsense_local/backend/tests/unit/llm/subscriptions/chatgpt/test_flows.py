import socket

import pytest

from api.config import get_settings
from modules.llm.subscriptions.chatgpt.flows import SignInFlows

pytestmark = pytest.mark.unit


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def test_in_a_container_a_new_sign_in_replaces_one_still_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The container's callback port is fixed, so only one sign-in can listen on it."""
    monkeypatch.setattr(get_settings(), "public_port", 4929)
    monkeypatch.setattr(get_settings(), "chatgpt_callback_port", _free_port())
    flows = SignInFlows()

    first = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]
    second = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]
    try:
        assert second.authorize_url
        assert flows.get(first.id) is None
        assert flows.get(second.id) is second
    finally:
        flows.cancel(second.id)
