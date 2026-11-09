import asyncio
import socket

import pytest

from api.config import get_settings
from modules.llm.subscriptions.chatgpt import flows as flows_module
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


def _in_a_container(monkeypatch: pytest.MonkeyPatch) -> int:
    port = _free_port()
    monkeypatch.setattr(get_settings(), "public_port", 4929)
    monkeypatch.setattr(get_settings(), "chatgpt_callback_port", port)
    return port


async def test_in_a_container_sign_ins_started_together_both_get_a_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two clicks at once: one replaces the other rather than both binding the port."""
    _in_a_container(monkeypatch)
    flows = SignInFlows()

    started = await asyncio.gather(
        flows.start(None, label=None, connection_id=None),  # type: ignore[arg-type]
        flows.start(None, label=None, connection_id=None),  # type: ignore[arg-type]
    )
    try:
        assert all(flow.authorize_url for flow in started)
    finally:
        for flow in started:
            flows.cancel(flow.id)


async def test_in_a_container_a_cancelled_sign_in_frees_the_port_at_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel, then sign in again straight away, before the cancelled task has run."""
    _in_a_container(monkeypatch)
    flows = SignInFlows()

    first = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]
    flows.cancel(first.id)
    second = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]
    try:
        assert second.authorize_url
    finally:
        flows.cancel(second.id)


async def test_in_a_container_a_sign_in_already_saving_is_left_to_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Its browser came back: replacing it would orphan a save that still commits."""
    port = _in_a_container(monkeypatch)
    exchanging = asyncio.Event()
    release = asyncio.Event()

    async def tokens(*_args: object) -> object:
        exchanging.set()
        await release.wait()
        return object()

    monkeypatch.setattr(flows_module, "_tokens", tokens)
    monkeypatch.setattr(flows_module, "_save", lambda *_args: (7, None))
    flows = SignInFlows()

    started = [await flows.start(None, label=None, connection_id=None)]  # type: ignore[arg-type]
    first = started[0]
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /callback?code=c&state=s HTTP/1.1\r\nHost: x\r\n\r\n")
        await writer.drain()
        await reader.read()
        writer.close()
        # Bounded: a callback that never reaches the exchange fails here, not hangs.
        await asyncio.wait_for(exchanging.wait(), timeout=5)

        second = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]
        started.append(second)
        assert second.authorize_url
        assert flows.get(first.id) is first
        release.set()
        assert first.task is not None
        await asyncio.wait_for(first.task, timeout=5)
        assert first.status == "signed_in"
        assert first.connection_id == 7
    finally:
        # Whatever failed above, nothing is left blocked or listening.
        release.set()
        for flow in started:
            flows.cancel(flow.id)


async def test_a_pasted_callback_address_finishes_the_sign_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From another machine the redirect to 127.0.0.1 fails in the user's own
    browser; the address it left there carries the code, and the API finishes
    with the verifier it kept."""
    _in_a_container(monkeypatch)
    seen: list[dict[str, str]] = []

    async def tokens(query: dict[str, str], *_args: object) -> object:
        seen.append(query)
        return object()

    monkeypatch.setattr(flows_module, "_tokens", tokens)
    monkeypatch.setattr(flows_module, "_save", lambda *_args: (7, None))
    flows = SignInFlows()
    flow = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]

    pasted = flows.paste(
        flow.id, "http://127.0.0.1:4929/callback?code=the-code&state=the-state"
    )

    assert pasted is True
    assert flow.task is not None
    await asyncio.wait_for(flow.task, timeout=5)
    assert seen == [{"code": "the-code", "state": "the-state"}]
    assert flow.status == "signed_in"


async def test_an_address_that_is_not_the_callback_is_refused_and_the_sign_in_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Another page's address, a callback without its code, or no address at all."""
    _in_a_container(monkeypatch)
    flows = SignInFlows()
    flow = await flows.start(None, label=None, connection_id=None)  # type: ignore[arg-type]
    try:
        assert flows.paste(flow.id, "https://chatgpt.com/?code=x&state=y") is False
        assert flows.paste(flow.id, "http://127.0.0.1:4929/callback?state=y") is False
        assert flows.paste(flow.id, "not an address") is False
        assert flow.status == "waiting"
    finally:
        flows.cancel(flow.id)


async def test_pasting_into_a_sign_in_that_is_gone_is_refused() -> None:
    """Cancelled, finished or never started: nothing to finish."""
    assert (
        SignInFlows().paste("no-such-flow", "http://127.0.0.1/callback?code=c&state=s")
        is False
    )
