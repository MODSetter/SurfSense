"""Keep-alive holders, rotation, the idle pool and unique sticky-exit leases.

Holders run direct (no proxy configured) against a server on 127.0.0.1, so the
connection counts are real and nothing reaches the network.
"""

import asyncio
from urllib.parse import urlsplit

import pytest

from proprietary.scraping import http, sessions
from proprietary.scraping.config import Config
from proprietary.scraping.proxy import registry
from proprietary.scraping.tests._local_http import LocalServer

_DI_URL = (
    "http://tok123__cr.us:secret@gw.dataimpulse.com:823"  # pragma: allowlist secret
)


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_active_provider", None)
    monkeypatch.setattr(Config, "PROXY_PROVIDER", None)
    monkeypatch.setattr(Config, "PROXY_URL", None)
    monkeypatch.setattr(sessions, "_leased", {})
    monkeypatch.setattr(sessions, "_quarantined", {})
    monkeypatch.setattr(sessions, "_idle", {})
    monkeypatch.setattr(sessions, "_reaper", None)


@pytest.fixture
def dataimpulse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "PROXY_PROVIDER", "dataimpulse")
    monkeypatch.setattr(Config, "PROXY_URL", _DI_URL)


def _port(exit: sessions.Exit) -> int:
    return urlsplit(exit.proxy_url()).port


def test_leases_never_share_a_port(dataimpulse: None) -> None:
    exits = [sessions.lease_exit("yt") for _ in range(300)]

    assert len({_port(e) for e in exits}) == 300
    assert all(e.sticky.startswith("yt") and e.sticky.isalnum() for e in exits)


def test_a_held_slot_is_skipped_and_a_released_one_reused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three slots in all: three leases fill them, the fourth must wait for one."""
    monkeypatch.setattr(
        registry.get_active_provider().__class__,
        "sticky_slot",
        lambda self, sid: int(sid[-1], 16) % 3,
    )
    held = [sessions.lease_exit("a") for _ in range(3)]

    assert len({int(e.sticky[-1], 16) % 3 for e in held}) == 3
    with pytest.raises(RuntimeError):
        sessions.lease_exit("a")

    sessions.release_exit(held[0])
    again = sessions.lease_exit("a")
    assert int(again.sticky[-1], 16) % 3 == int(held[0].sticky[-1], 16) % 3


def test_a_burned_slot_is_quarantined(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        registry.get_active_provider().__class__,
        "sticky_slot",
        lambda self, sid: int(sid[-1], 16) % 2,
    )
    first, second = sessions.lease_exit("a"), sessions.lease_exit("a")
    sessions.release_exit(first, burned=True)

    with pytest.raises(RuntimeError):
        sessions.lease_exit("a")  # one slot burned, the other held

    monkeypatch.setattr(sessions, "BURN_QUARANTINE_S", 0.0)
    sessions.release_exit(second, burned=True)
    assert sessions.lease_exit("a").sticky


def test_release_is_idempotent_and_the_gateway_is_never_leased(
    dataimpulse: None,
) -> None:
    exit = sessions.lease_exit("x")
    sessions.release_exit(exit)
    sessions.release_exit(exit)
    sessions.release_exit(sessions.Exit("us"))

    assert sessions._leased == {}


def test_exit_urls(dataimpulse: None) -> None:
    gateway = sessions.Exit("GB")
    sticky = sessions.lease_exit("r", "de")

    assert gateway.country == "gb"
    assert urlsplit(gateway.proxy_url()).port == 823
    assert urlsplit(gateway.proxy_url()).username == "tok123__cr.gb"
    assert 10000 <= _port(sticky) <= 20000
    assert urlsplit(sticky.proxy_url()).username == "tok123__cr.de"
    assert sticky.playwright_proxy()["server"].endswith(f":{_port(sticky)}")


def test_no_proxy_configured_means_direct() -> None:
    assert sessions.Exit().proxy_url() is None
    assert sessions.lease_exit("x").proxy_url() is None


@pytest.mark.asyncio
async def test_a_holder_keeps_one_connection_and_closes_it() -> None:
    async with LocalServer() as server:
        async with sessions.holder("test") as h:
            first = await h.request("GET", f"{server.base}/ok", stage="a")
            second = await h.request("GET", f"{server.base}/ok", stage="b")
            assert sessions.live_sessions() == 1
        await asyncio.sleep(0.1)

    assert first.timings.new_conn and not second.timings.new_conn
    assert server.connections == 1
    assert h.uses == 2
    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_rotate_opens_a_new_connection_and_leases_a_new_sticky(
    dataimpulse: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Direct to the local server: only the exits are under test here.
    monkeypatch.setattr(sessions.Exit, "proxy_url", lambda self: None)
    async with LocalServer() as server:
        h = sessions.SessionHolder("test", sessions.Exit())
        await h.request("GET", f"{server.base}/ok", stage="a")
        await h.rotate("blocked")
        await h.request("GET", f"{server.base}/ok", stage="b")
        await h.close()

    assert server.connections == 2
    assert h.rotations == 1
    assert h.exit == sessions.Exit()  # the gateway stays the gateway

    sticky = sessions.SessionHolder("test", sessions.Exit(sticky="mine"))
    await sticky.rotate("blocked", country="gb")
    assert sticky.exit.sticky not in (None, "mine")
    assert sticky.exit.country == "gb"
    assert len(sessions._leased) == 1
    await sticky.close()
    assert sessions._leased == {}


@pytest.mark.asyncio
async def test_rotate_lets_a_request_in_flight_finish_on_the_old_session() -> None:
    async with LocalServer() as server:
        async with sessions.holder("test") as h:
            slow = asyncio.create_task(
                h.request("GET", f"{server.base}/slow?s=0.5", stage="slow")
            )
            await asyncio.sleep(0.2)
            await h.rotate("blocked")
            assert sessions.live_sessions() == 1  # the old one is still serving
            fresh = await h.request("GET", f"{server.base}/ok", stage="fresh")
            old = await slow

        assert old.status == 200 and fresh.status == 200
        assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_burn_rotates_before_the_next_request() -> None:
    async with LocalServer() as server, sessions.holder("test") as h:
        await h.request("GET", f"{server.base}/ok", stage="a")
        h.burn("captcha")
        assert h.burned
        await h.request("GET", f"{server.base}/ok", stage="b")
        assert not h.burned

    assert server.connections == 2
    assert h.rotations == 1


@pytest.mark.asyncio
async def test_max_uses_rotates_proactively() -> None:
    async with LocalServer() as server, sessions.holder("test", max_uses=2) as h:
        for _ in range(5):
            await h.request("GET", f"{server.base}/ok", stage="a")

    assert server.connections == 3
    assert h.rotations == 2


@pytest.mark.asyncio
async def test_max_streams_bounds_one_holder() -> None:
    async with LocalServer() as server, sessions.holder("test", max_streams=2) as h:
        await asyncio.gather(
            *(
                h.request("GET", f"{server.base}/slow?s=0.2", stage="s")
                for _ in range(5)
            )
        )

    assert server.max_inflight == 2


@pytest.mark.asyncio
async def test_a_failing_block_closes_its_holder() -> None:
    async with LocalServer() as server:
        with pytest.raises(ValueError):
            async with sessions.holder("test", keep_idle=True) as h:
                await h.request("GET", f"{server.base}/ok", stage="a")
                raise ValueError("parse failed")

    assert sessions.live_sessions() == 0
    assert sessions._idle == {}


@pytest.mark.asyncio
async def test_keep_idle_hands_the_warm_session_to_the_next_call() -> None:
    async with LocalServer() as server:
        async with sessions.holder("yt", keep_idle=True) as first:
            await first.request("GET", f"{server.base}/ok", stage="a")
            assert first._conn.session.cookies.get("a") == "1"
        async with sessions.holder("yt", keep_idle=True) as second:
            assert second is first
            assert second._conn.session.cookies.get("a") is None  # cleared
            again = await second.request("GET", f"{server.base}/ok", stage="b")
        async with sessions.holder("gmaps", keep_idle=True) as other:
            assert other is not first  # never across plugins
        await sessions.close_idle()

    assert not again.timings.new_conn
    assert server.connections == 1
    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_uses_carry_across_calls_on_a_kept_session() -> None:
    """max_uses bounds the requests one exit serves, whichever calls sent them."""
    async with LocalServer() as server:
        for _ in range(3):
            async with sessions.holder("yt", keep_idle=True, max_uses=2) as h:
                await h.request("GET", f"{server.base}/ok", stage="a")
        await sessions.close_idle()

    assert h.rotations == 1
    assert server.connections == 2


@pytest.mark.asyncio
async def test_a_sticky_session_is_never_kept() -> None:
    exit = sessions.lease_exit("yt")
    async with (
        LocalServer() as server,
        sessions.holder("yt", exit, keep_idle=True) as h,
    ):
        await h.request("GET", f"{server.base}/ok", stage="a")

    assert sessions._idle == {}
    assert sessions.live_sessions() == 0
    sessions.release_exit(exit)


@pytest.mark.asyncio
async def test_a_burned_session_is_never_kept() -> None:
    async with LocalServer() as server, sessions.holder("yt", keep_idle=True) as h:
        await h.request("GET", f"{server.base}/ok", stage="a")
        h.burn("blocked")

    assert sessions._idle == {}
    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_the_idle_pool_is_capped_and_expires(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "MAX_IDLE_SESSIONS", 2)
    monkeypatch.setattr(sessions, "IDLE_TTL_S", 0.3)
    async with LocalServer() as server:

        async def call(plugin: str) -> None:
            async with sessions.holder(plugin, keep_idle=True) as h:
                await h.request("GET", f"{server.base}/ok", stage="a")

        await asyncio.gather(call("a"), call("b"), call("c"))
        await asyncio.sleep(0.05)
        assert sum(len(v) for v in sessions._idle.values()) == 2
        assert sessions.live_sessions() == 2
        await asyncio.sleep(0.6)  # the reaper closes them at the TTL

    assert sessions._idle == {}
    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_keep_idle_off_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Config, "MAX_IDLE_SESSIONS", 0)
    async with LocalServer() as server, sessions.holder("yt", keep_idle=True) as h:
        await h.request("GET", f"{server.base}/ok", stage="a")

    assert sessions._idle == {}
    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_bind_and_current() -> None:
    assert sessions.current() is None
    async with sessions.bound("test") as h:
        assert sessions.current() is h

        async def child() -> object:
            return sessions.current()

        assert await asyncio.create_task(child()) is h
    assert sessions.current() is None


async def _half_body(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    """Promises 1000 bytes, sends 10, then hangs up: a body cut off mid-transfer."""
    await reader.readuntil(b"\r\n\r\n")
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 1000\r\n\r\n<html>part")
    await writer.drain()
    await asyncio.sleep(0.6)
    writer.close()


@pytest.mark.asyncio
async def test_closing_a_holder_mid_body_never_returns_a_truncated_page() -> None:
    server = await asyncio.start_server(_half_body, "127.0.0.1", 0)
    url = f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/"
    try:
        h = sessions.SessionHolder("test", sessions.Exit())
        task = asyncio.create_task(h.request("GET", url, stage="x", timeout=(1, 3)))
        await asyncio.sleep(0.3)
        await h.close()
        with pytest.raises(http.TransportError):
            await task
    finally:
        server.close()

    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_closing_a_holder_lets_a_request_in_flight_finish() -> None:
    async with LocalServer() as server:
        h = sessions.SessionHolder("test", sessions.Exit())
        slow = asyncio.create_task(
            h.request("GET", f"{server.base}/slow?s=0.4", stage="slow")
        )
        await asyncio.sleep(0.15)
        await h.close()
        assert sessions.live_sessions() == 1  # still serving the request
        r = await slow

    assert (r.status, r.body) == (200, b"slow")
    assert sessions.live_sessions() == 0  # its last request closed it


@pytest.mark.asyncio
async def test_a_closed_holder_refuses_requests_and_opens_nothing(
    dataimpulse: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions.Exit, "proxy_url", lambda self: None)
    async with LocalServer() as server:
        async with sessions.holder("test", sessions.Exit(sticky="mine")) as h:
            await h.request("GET", f"{server.base}/ok", stage="a")
        with pytest.raises(http.TransportError) as caught:
            await h.request("GET", f"{server.base}/ok", stage="late")
        await h.rotate("SessionClosed")  # what a rotation loop does next

    assert caught.value.kind == "SessionClosed"
    assert sessions.live_sessions() == 0
    assert server.connections == 1
    assert h.rotations == 0
    assert sessions._leased == {}  # the no-op rotate leased nothing


@pytest.mark.asyncio
async def test_a_holder_with_a_request_in_flight_is_not_kept_idle() -> None:
    async with LocalServer() as server:
        async with sessions.holder("yt", keep_idle=True) as h:
            await h.request("GET", f"{server.base}/ok", stage="a")
            background = asyncio.create_task(
                h.request("GET", f"{server.base}/slow?s=0.3", stage="bg")
            )
            await asyncio.sleep(0.1)
        assert sessions._idle == {}
        r = await background
        await sessions.close_idle()

    assert r.status == 200
    assert sessions.live_sessions() == 0


@pytest.mark.asyncio
async def test_tasks_refused_on_one_exit_rotate_it_once() -> None:
    async with LocalServer() as server, sessions.holder("test") as h:

        async def task() -> None:
            seen = h.rotations
            r = await h.request("GET", f"{server.base}/status/403", stage="a")
            if r.blocked:
                await h.rotate("blocked", seen=seen)

        await asyncio.gather(*(task() for _ in range(4)))
        assert h.rotations == 1
        await h.rotate("country", country="gb")  # without seen it always rotates
        assert h.rotations == 2


@pytest.mark.asyncio
async def test_one_plugin_cannot_evict_the_others_idle_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "MAX_IDLE_SESSIONS", 4)
    async with LocalServer() as server:

        async def call(plugin: str) -> None:
            async with sessions.holder(plugin, keep_idle=True) as h:
                await h.request("GET", f"{server.base}/ok", stage="a")

        await call("gmaps")
        await asyncio.gather(*(call("yt") for _ in range(6)))
        await asyncio.sleep(0.05)
        kept = [k[0] for k, v in sessions._idle.items() for _ in v]
        assert sorted(kept) == ["gmaps", "yt", "yt", "yt"]
        await sessions.close_idle()

    assert sessions.live_sessions() == 0
