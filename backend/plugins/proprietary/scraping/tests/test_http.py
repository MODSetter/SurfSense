"""The fail-fast transport: one attempt, split timeouts, raw bytes, one perf line.

Every test runs against sockets on 127.0.0.1; nothing reaches the network.
"""

import asyncio
import logging
import time
from weakref import WeakKeyDictionary

import pytest

from proprietary.scraping import http
from proprietary.scraping.config import Config
from proprietary.scraping.tests._local_http import Blackhole, LocalServer


def test_fail_fast_is_one_attempt_with_split_timeouts() -> None:
    """Scrapling call sites splat it: (connect, read), and retries=1 is one try."""
    assert http.FAIL_FAST == {"timeout": (5, 15), "retries": 1, "retry_delay": 0}


@pytest.mark.asyncio
async def test_a_dead_exit_fails_at_the_connect_timeout_without_retrying() -> None:
    """The proxy accepts and never answers the CONNECT: one connection, ~0.5 s."""
    async with Blackhole() as hole:
        started = time.monotonic()
        with pytest.raises(http.TransportError) as caught:
            await http.request(
                "GET",
                "https://example.com/",
                plugin="test",
                stage="dead",
                proxy=hole.proxy,
                timeout=(0.5, 5),
            )
        elapsed = time.monotonic() - started
        await asyncio.sleep(0.2)

    assert caught.value.kind == "Timeout"
    assert caught.value.code == 28
    assert "timed out" in caught.value.detail
    assert elapsed < 2.0  # the read part (5 s) never starts
    assert hole.connections == 1
    assert "pa55word" not in str(caught.value)


@pytest.mark.asyncio
async def test_a_silent_response_fails_at_connect_plus_read() -> None:
    """Plain HTTP through the proxy: the request is sent, no byte comes back."""
    async with Blackhole() as hole:
        started = time.monotonic()
        with pytest.raises(http.TransportError) as caught:
            await http.request(
                "GET",
                "http://example.com/",
                plugin="test",
                stage="silent",
                proxy=hole.proxy,
                timeout=(0.3, 0.7),
            )
        elapsed = time.monotonic() - started
        await asyncio.sleep(0.2)

    assert caught.value.kind == "Timeout"
    assert 0.9 <= elapsed < 2.5
    assert hole.connections == 1


@pytest.mark.asyncio
async def test_returns_raw_bytes_headers_cookies_and_timings() -> None:
    async with LocalServer() as server:
        r = await http.request(
            "GET", f"{server.base}/ok", plugin="test", stage="ok", proxy=None
        )

    assert r.status == 200
    assert r.body == b"hello"
    assert r.text() == "hello"
    assert r.headers["content-type"] == "text/plain; charset=utf-8"
    assert r.headers["Content-Type"] == "text/plain; charset=utf-8"
    assert r.cookies == {"a": "1"}
    assert r.history == ()
    assert r.timings.new_conn is True
    assert r.timings.total_ms > 0
    assert r.timings.bytes_wire >= len(b"hello")
    assert r.blocked is False


@pytest.mark.asyncio
async def test_text_uses_the_declared_charset() -> None:
    async with LocalServer() as server:
        r = await http.request(
            "GET", f"{server.base}/latin", plugin="test", stage="t", proxy=None
        )

    assert r.body == b"caf\xe9"
    assert r.text() == "café"


def test_text_falls_back_to_utf8_on_an_unknown_charset() -> None:
    r = http.RawResponse(
        status=200,
        url="u",
        headers={"content-type": "text/html; charset=nonsense"},
        cookies={},
        body="café".encode(),
        history=(),
        timings=http.Timings(False, 0, 0, 0, 0, 0),
    )

    assert r.text() == "café"


@pytest.mark.asyncio
async def test_json_and_location() -> None:
    async with LocalServer() as server:
        r = await http.request(
            "GET", f"{server.base}/json", plugin="test", stage="j", proxy=None
        )
        hop = await http.request(
            "GET",
            f"{server.base}/redirect",
            plugin="test",
            stage="r",
            proxy=None,
            allow_redirects=False,
        )
        followed = await http.request(
            "GET", f"{server.base}/redirect", plugin="test", stage="r", proxy=None
        )

    assert r.json() == {"a": [1, 2]}
    assert hop.status == 302
    assert hop.location() == "/ok"
    assert followed.status == 200
    assert followed.url == f"{server.base}/ok"
    assert followed.history == (f"{server.base}/redirect",)


@pytest.mark.asyncio
async def test_google_referer_by_default_and_opt_out() -> None:
    """Parity with Scrapling's stealthy_headers, which add only this referer."""
    async with LocalServer() as server:
        await http.request(
            "GET", f"{server.base}/echo", plugin="test", stage="e", proxy=None
        )
        await http.request(
            "GET",
            f"{server.base}/echo",
            plugin="test",
            stage="e",
            proxy=None,
            referer=None,
        )
        await http.request(
            "GET",
            f"{server.base}/echo",
            plugin="test",
            stage="e",
            proxy=None,
            headers={"Referer": "https://example.com/"},
        )

    first, second, third = (r["headers"] for r in server.requests)
    assert first["referer"] == http.GOOGLE
    assert "referer" not in second
    assert third["referer"] == "https://example.com/"


@pytest.mark.asyncio
async def test_a_kept_session_reuses_its_connection() -> None:
    async with LocalServer() as server:
        session = http.open_session()
        try:
            first = await http.request(
                "GET",
                f"{server.base}/ok",
                plugin="test",
                stage="a",
                proxy=None,
                session=session,
            )
            second = await http.request(
                "GET",
                f"{server.base}/ok",
                plugin="test",
                stage="b",
                proxy=None,
                session=session,
            )
        finally:
            await session.close()

    assert first.timings.new_conn is True
    assert second.timings.new_conn is False
    assert server.connections == 1


@pytest.mark.asyncio
async def test_the_perf_line_has_every_field_and_never_the_proxy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Through a plain-HTTP proxy with credentials, as in production."""
    caplog.set_level(logging.INFO, logger=http.__name__)
    async with LocalServer() as server:
        proxy = (
            f"http://user:pa55word@127.0.0.1:{server.port}"  # pragma: allowlist secret
        )
        r = await http.request(
            "GET",
            "http://example.test/status/403",
            plugin="amazon",
            stage="pdp",
            proxy=proxy,
            attempt=2,
        )

    assert r.status == 403
    assert r.blocked is True
    line = next(m for m in caplog.messages if m.startswith("[amazon][perf]"))
    for field in (
        "stage=pdp",
        "status=403",
        "ms=",
        "queue_ms=",
        "new_conn=1",
        "connect_ms=",
        "tls_ms=",
        "ttfb_ms=",
        "bytes=7",
        "attempt=2",
        "hedge=0",
        "blocked=1",
        "host=example.test",
    ):
        assert field in line
    assert "pa55word" not in caplog.text


@pytest.mark.asyncio
async def test_a_plugin_predicate_decides_blocked() -> None:
    async with LocalServer() as server:
        r = await http.request(
            "GET",
            f"{server.base}/ok",
            plugin="test",
            stage="s",
            proxy=None,
            is_blocked=lambda resp: b"hello" in resp.body,
        )

    assert r.status == 200
    assert r.blocked is True


@pytest.mark.asyncio
async def test_a_failure_logs_its_perf_line(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=http.__name__)
    async with Blackhole() as hole:
        with pytest.raises(http.TransportError):
            await http.request(
                "GET",
                "https://example.com/",
                plugin="walmart",
                stage="search",
                proxy=hole.proxy,
                timeout=(0.3, 1),
            )

    line = next(m for m in caplog.messages if m.startswith("[walmart][perf]"))
    assert "status=0 err=Timeout" in line
    assert "pa55word" not in caplog.text


@pytest.mark.asyncio
async def test_the_process_wide_bound_holds_requests_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(Config, "MAX_HTTP", 2)
    monkeypatch.setattr(http, "_inflight", WeakKeyDictionary())
    caplog.set_level(logging.INFO, logger=http.__name__)
    async with LocalServer() as server:
        await asyncio.gather(
            *(
                http.request(
                    "GET",
                    f"{server.base}/slow?s=0.2",
                    plugin="test",
                    stage="b",
                    proxy=None,
                )
                for _ in range(5)
            )
        )

    assert server.max_inflight == 2
    waits = [m for m in caplog.messages if "[test][perf]" in m]
    assert any("queue_ms=0 " not in m for m in waits)


@pytest.mark.asyncio
async def test_cancelling_a_request_releases_its_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Config, "MAX_HTTP", 1)
    monkeypatch.setattr(http, "_inflight", WeakKeyDictionary())
    async with LocalServer() as server:
        task = asyncio.create_task(
            http.request(
                "GET", f"{server.base}/slow?s=5", plugin="t", stage="c", proxy=None
            )
        )
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        r = await asyncio.wait_for(
            http.request("GET", f"{server.base}/ok", plugin="t", stage="c", proxy=None),
            timeout=3,
        )

    assert r.status == 200


@pytest.mark.asyncio
async def test_a_session_closed_under_a_request_raises_not_an_empty_response(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """curl_cffi resolves the request with status 0 and no body; that is no response."""
    caplog.set_level(logging.INFO)
    async with LocalServer() as server:
        session = http.open_session()
        task = asyncio.create_task(
            http.request(
                "GET",
                f"{server.base}/slow?s=1.0",
                plugin="test",
                stage="closed",
                proxy=None,
                session=session,
            )
        )
        await asyncio.sleep(0.2)
        await session.close()
        with pytest.raises(http.TransportError) as caught:
            await task

    assert caught.value.kind == "SessionClosed"
    assert any("stage=closed status=0 err=SessionClosed" in m for m in caplog.messages)
