import asyncio
import socket

import pytest

from api.config import get_settings
from modules.llm.subscriptions.chatgpt.loopback import Loopback

pytestmark = pytest.mark.unit


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


async def _browser_returns(port: int, query: str) -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET /callback?{query} HTTP/1.1\r\nHost: x\r\n\r\n".encode())
    await writer.drain()
    await reader.read()
    writer.close()


async def test_on_the_desktop_openai_returns_to_the_port_it_listens_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A free port of its own, which the browser on this machine reaches."""
    monkeypatch.setattr(get_settings(), "public_port", None)
    monkeypatch.setattr(get_settings(), "chatgpt_callback_port", 0)
    loopback = Loopback()
    redirect = await loopback.open()
    try:
        port = int(redirect.removeprefix("http://127.0.0.1:").removesuffix("/callback"))
        await _browser_returns(port, "code=c&state=s")
        assert await loopback.callback() == {"code": "c", "state": "s"}
    finally:
        loopback.close()


async def test_in_a_container_openai_returns_through_the_published_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The browser cannot reach a port inside the container; Caddy forwards `/callback` to this one."""
    listen = _free_port()
    monkeypatch.setattr(get_settings(), "public_port", 4929)
    monkeypatch.setattr(get_settings(), "chatgpt_callback_port", listen)
    loopback = Loopback()
    redirect = await loopback.open()
    try:
        assert redirect == "http://127.0.0.1:4929/callback"
        await _browser_returns(listen, "code=c&state=s")
        assert await loopback.callback() == {"code": "c", "state": "s"}
    finally:
        loopback.close()
