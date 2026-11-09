"""One proxied HTTP request that fails fast, returns raw bytes and logs one perf line.

Scrapling's fetchers retry three times on the same exit with 1 s sleeps, give a dead
exit 30 s to connect, and lxml-parse every body on the event loop. :func:`request`
sends exactly one attempt with a split (connect, read) timeout and hands back the
body as bytes, for the plugin to decode and parse in its own ``to_thread`` step. The
plugin's rotation loop stays the only retry layer.

Call sites still on Scrapling pass :data:`FAIL_FAST` to get the same timeouts and no
hidden retries.
"""

from __future__ import annotations

import asyncio
import json as _json
import logging
import time
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urlsplit
from weakref import WeakKeyDictionary

from curl_cffi.const import CurlInfo
from curl_cffi.curl import CurlError
from curl_cffi.requests import AsyncSession

from proprietary.scraping.config import Config

try:  # about 5x faster on the large embedded JSON blobs the plugins read
    import orjson
except ImportError:  # pragma: no cover - orjson ships with the host image
    orjson = None

logger = logging.getLogger(__name__)

# For Scrapling call sites: AsyncFetcher.get/post(..., **FAIL_FAST) or
# FetcherSession(..., **FAIL_FAST). curl_cffi reads the tuple as (connect, read):
# the connect part covers the proxy CONNECT and the TLS handshake, and the whole
# request is capped at their sum. retries=1 is one attempt (Scrapling's default is 3,
# with 1 s sleeps, on the same exit).
FAIL_FAST: dict[str, Any] = {"timeout": (5, 15), "retries": 1, "retry_delay": 0}

DEFAULT_TIMEOUT: tuple[float, float] = (5, 15)

# Scrapling's stealthy_headers add only this referer when curl impersonates a
# browser; keeping it as the default keeps request shape unchanged for the sites.
GOOGLE = "https://www.google.com/"

# Statuses every site uses for "this exit is refused"; plugins pass their own
# predicate for body markers (captcha pages, google.com/sorry, challenge pages).
BLOCK_STATUSES = frozenset({403, 429, 444})

# Set by concurrency.hedged for each attempt it starts, so requests inside a hedge
# say so on their perf line without the plugin threading a flag through.
HEDGE_INDEX: ContextVar[int] = ContextVar("scraping_hedge_index", default=0)

_TIMING_INFOS = [
    CurlInfo.NUM_CONNECTS,
    CurlInfo.CONNECT_TIME,
    CurlInfo.APPCONNECT_TIME,
    CurlInfo.STARTTRANSFER_TIME,
    CurlInfo.TOTAL_TIME,
    CurlInfo.SIZE_DOWNLOAD_T,
    CurlInfo.HEADER_SIZE,
]

# One bound per event loop: the host's request loop in production, one per test.
_inflight: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    WeakKeyDictionary()
)


@dataclass(frozen=True)
class Timings:
    """Where one request's time went, from curl's own clocks (all ms)."""

    new_conn: bool  # False when a kept connection served it: no CONNECT, no TLS
    connect_ms: float  # TCP to the proxy (or the site when direct)
    tls_ms: float  # proxy CONNECT tunnel plus TLS to the site; 0 on a kept connection
    ttfb_ms: float
    total_ms: float
    bytes_wire: int  # headers plus body as received, before decompression


@dataclass(frozen=True)
class RawResponse:
    """A response as bytes; nothing is parsed until the plugin asks."""

    status: int
    url: str  # after redirects
    headers: Mapping[str, str]  # case-insensitive; repeated headers joined by ", "
    cookies: dict[str, str]  # what the final response set
    body: bytes
    history: tuple[str, ...]  # redirect hops before `url`
    timings: Timings
    blocked: bool = False

    def text(self) -> str:
        """The body decoded with the Content-Type charset, else UTF-8, never raising."""
        charset = _charset(self.headers.get("content-type"))
        try:
            return self.body.decode(charset or "utf-8", errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        if orjson is not None:
            return orjson.loads(self.body)
        return _json.loads(self.body)

    def location(self) -> str | None:
        """The redirect target, when redirects were not followed."""
        return self.headers.get("location")


class TransportError(Exception):
    """The request got no response: a timeout, a dead exit, a refused tunnel.

    ``kind`` is curl_cffi's error class name (``Timeout``, ``ProxyError``,
    ``ConnectionError``, ``SSLError``, ``TooManyRedirects``, ...), or
    ``SessionClosed`` when the session was closed before the response completed;
    ``code`` is curl's error number (28 is a timeout; 0 for ``SessionClosed``);
    ``detail`` is curl's own sentence, such as "CONNECT tunnel failed, response
    407". curl never puts the proxy's credentials in it.
    """

    def __init__(
        self, kind: str, code: int, elapsed_ms: float, detail: str = ""
    ) -> None:
        super().__init__(f"{kind} (curl {code}) after {elapsed_ms:.0f} ms: {detail}")
        self.kind = kind
        self.code = code
        self.elapsed_ms = elapsed_ms
        self.detail = detail


def open_session(*, max_clients: int = 10) -> AsyncSession:
    """A curl_cffi session that records the timings the perf line needs.

    Connections are kept inside it until ``await session.close()``. Prefer
    :func:`proprietary.scraping.sessions.holder`, which owns the close.
    """
    return AsyncSession(curl_infos=list(_TIMING_INFOS), max_clients=max_clients)


def default_blocked(response: RawResponse) -> bool:
    return response.status in BLOCK_STATUSES


async def request(
    method: str,
    url: str,
    *,
    plugin: str,
    stage: str,
    proxy: str | None,
    session: AsyncSession | None = None,
    headers: Mapping[str, str] | None = None,
    cookies: Mapping[str, str] | None = None,
    params: Any = None,
    data: Any = None,
    json: Any = None,
    referer: str | None = GOOGLE,
    # curl enforces it (connect, then the whole request), so a cancel is not needed.
    timeout: tuple[float, float] = DEFAULT_TIMEOUT,  # noqa: ASYNC109
    allow_redirects: bool | str = "safe",
    max_redirects: int = 5,
    impersonate: str = "chrome",
    attempt: int = 0,
    hedge: bool = False,
    is_blocked: Callable[[RawResponse], bool] | None = None,
) -> RawResponse:
    """Send one request, with no retry, and log one ``[<plugin>][perf]`` line.

    Without ``session`` it opens and closes a one-off session, paying a fresh
    CONNECT and TLS. Raises :class:`TransportError` when no complete response
    arrives; any HTTP status, 4xx and 5xx included, comes back as a response.
    """
    merged = dict(headers or {})
    if referer is not None and not any(k.lower() == "referer" for k in merged):
        merged["referer"] = referer
    own = session is None
    sess = open_session() if own else session
    hedge_index = max(int(hedge), HEDGE_INDEX.get())
    host = urlsplit(url).hostname or ""
    queued = time.perf_counter()
    try:
        async with _semaphore():
            started = time.perf_counter()
            queue_ms = (started - queued) * 1000
            try:
                rsp = await sess.request(
                    method,
                    url,
                    headers=merged,
                    cookies=dict(cookies) if cookies else None,
                    params=params,
                    data=data,
                    json=json,
                    proxy=proxy,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    max_redirects=max_redirects,
                    impersonate=impersonate,
                )
            except CurlError as e:
                elapsed = (time.perf_counter() - started) * 1000
                timings = _timings(getattr(e, "response", None), elapsed)
                _log_failure(
                    plugin,
                    stage,
                    type(e).__name__,
                    elapsed,
                    queue_ms,
                    timings,
                    attempt,
                    hedge_index,
                    host,
                )
                raise TransportError(
                    type(e).__name__, e.code, elapsed, _curl_detail(e)
                ) from None
            elapsed = (time.perf_counter() - started) * 1000
            # curl_cffi resolves a request whose session closes under it with what
            # had arrived (status 0, or a 200 with half its body), not an error.
            if getattr(sess, "_closed", False) or not rsp.status_code:
                _log_failure(
                    plugin,
                    stage,
                    "SessionClosed",
                    elapsed,
                    queue_ms,
                    _timings(rsp, elapsed),
                    attempt,
                    hedge_index,
                    host,
                )
                raise TransportError(
                    "SessionClosed",
                    0,
                    elapsed,
                    "session closed before the response completed",
                )
    finally:
        if own:
            await sess.close()

    response = RawResponse(
        status=rsp.status_code,
        url=rsp.url,
        headers=rsp.headers,
        cookies={c.name: c.value or "" for c in rsp.cookies.jar},
        body=rsp.content,
        history=tuple(h.url for h in rsp.history),
        timings=_timings(rsp, elapsed),
    )
    blocked = (is_blocked or default_blocked)(response)
    if blocked:
        response = replace(response, blocked=True)
    logger.info(
        "[%s][perf] stage=%s status=%d ms=%.0f queue_ms=%.0f %s bytes=%d "
        "attempt=%d hedge=%d blocked=%d host=%s",
        plugin,
        stage,
        response.status,
        elapsed,
        queue_ms,
        _timing_fields(response.timings),
        len(response.body),
        attempt,
        hedge_index,
        int(blocked),
        host,
    )
    return response


def _log_failure(
    plugin: str,
    stage: str,
    kind: str,
    elapsed: float,
    queue_ms: float,
    timings: Timings,
    attempt: int,
    hedge_index: int,
    host: str,
) -> None:
    logger.info(
        "[%s][perf] stage=%s status=0 err=%s ms=%.0f queue_ms=%.0f %s "
        "bytes=0 attempt=%d hedge=%d blocked=0 host=%s",
        plugin,
        stage,
        kind,
        elapsed,
        queue_ms,
        _timing_fields(timings),
        attempt,
        hedge_index,
        host,
    )


def _semaphore() -> asyncio.Semaphore:
    """The process-wide bound, made on first use in the running loop."""
    loop = asyncio.get_running_loop()
    bound = _inflight.get(loop)
    if bound is None:
        bound = _inflight[loop] = asyncio.Semaphore(max(1, Config.MAX_HTTP))
    return bound


def _timings(rsp: Any, elapsed_ms: float) -> Timings:
    infos = getattr(rsp, "infos", None) or {}
    connect = float(infos.get(CurlInfo.CONNECT_TIME) or 0.0)
    app = float(infos.get(CurlInfo.APPCONNECT_TIME) or 0.0)
    total = infos.get(CurlInfo.TOTAL_TIME)
    return Timings(
        new_conn=int(infos.get(CurlInfo.NUM_CONNECTS) or 0) > 0,
        connect_ms=connect * 1000,
        tls_ms=max(0.0, app - connect) * 1000 if app else 0.0,
        ttfb_ms=float(infos.get(CurlInfo.STARTTRANSFER_TIME) or 0.0) * 1000,
        total_ms=float(total) * 1000 if total else elapsed_ms,
        bytes_wire=int(infos.get(CurlInfo.SIZE_DOWNLOAD_T) or 0)
        + int(infos.get(CurlInfo.HEADER_SIZE) or 0),
    )


def _timing_fields(t: Timings) -> str:
    return (
        f"new_conn={int(t.new_conn)} connect_ms={t.connect_ms:.0f} "
        f"tls_ms={t.tls_ms:.0f} ttfb_ms={t.ttfb_ms:.0f} total_ms={t.total_ms:.0f} "
        f"wire={t.bytes_wire}"
    )


def _curl_detail(error: CurlError) -> str:
    # "Failed to perform, curl: (28) Connection timed out after 515 milliseconds.
    # See https://curl.se/libcurl/c/libcurl-errors.html first for more details."
    text = str(error).split(" See https://", 1)[0]
    return text.split(") ", 1)[1] if text.startswith("Failed to perform") else text


def _charset(content_type: str | None) -> str | None:
    if not content_type:
        return None
    for part in content_type.split(";")[1:]:
        key, _, value = part.partition("=")
        if key.strip().lower() == "charset":
            return value.strip().strip("\"'") or None
    return None
