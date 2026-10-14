"""Keep-alive proxy sessions for one job, and sticky exits no two jobs share.

A one-off request pays 0.4-2.1 s of proxy CONNECT and TLS through a new exit; a
request on a kept connection skips both (google robots.txt: 1.55 s one-off, 0.34 s
reused). :func:`holder` gives a job one keep-alive session that it can rotate to a
new exit on a block, and :func:`bind` / :func:`current` let the job's fetch helpers
find it without threading a parameter through every parser.

DataImpulse hashes sticky ids onto 10,001 ports, so about 118 live ids give even
odds of two "independent" flows sharing one IP. :func:`lease_exit` hands out ids
whose port no other live lease holds.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import threading
import time
from collections import Counter
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from proprietary.scraping import http
from proprietary.scraping.config import Config
from proprietary.scraping.lifecycle import at_shutdown
from proprietary.scraping.proxy import get_geo_proxy_url, get_sticky_proxy_url
from proprietary.scraping.proxy.base import playwright_proxy
from proprietary.scraping.proxy.registry import get_active_provider

logger = logging.getLogger(__name__)

# A kept tunnel died after about 64 s idle (shared bench), so idle sessions go at 50.
IDLE_TTL_S = 50.0
# A burned sticky slot is not handed out again for this long.
BURN_QUARANTINE_S = 600.0
_LEASE_TRIES = 64

# Leases are also taken on the browser loop's thread, hence the lock.
_lease_lock = threading.Lock()
_leased: dict[object, str] = {}  # sticky slot -> the id holding it
_quarantined: dict[object, float] = {}  # sticky slot -> monotonic time it frees
_live_sessions = 0


@dataclass(frozen=True)
class Exit:
    """Where a session's traffic leaves the proxy.

    ``sticky=None`` is the rotating gateway: each new connection draws a new IP, and
    a kept connection keeps its IP. A sticky id pins one IP across connections.
    """

    country: str | None = None
    sticky: str | None = None

    def __post_init__(self) -> None:
        country = (self.country or "").strip().lower() or None
        object.__setattr__(self, "country", country)

    def proxy_url(self) -> str | None:
        """The proxy URL for this exit; ``None`` when no proxy is configured."""
        if self.sticky is not None:
            return get_sticky_proxy_url(self.sticky, self.country)
        return get_geo_proxy_url(self.country)

    def playwright_proxy(self) -> dict[str, str] | None:
        """The same exit as Playwright's proxy dict, for a browser on this IP."""
        return playwright_proxy(self.proxy_url())


def lease_exit(prefix: str, country: str | None = None) -> Exit:
    """A sticky exit whose IP slot no other live lease holds; release it after.

    Raises ``RuntimeError`` only when every try lands on a held slot, which takes
    thousands of live leases on DataImpulse.
    """
    provider = get_active_provider()
    safe_prefix = re.sub(r"[^A-Za-z0-9]", "", prefix)[:16]
    now = time.monotonic()
    with _lease_lock:
        for _ in range(_LEASE_TRIES):
            sticky = f"{safe_prefix}{secrets.token_hex(6)}"
            slot = provider.sticky_slot(sticky)
            if slot in _leased:
                continue
            frees_at = _quarantined.get(slot)
            if frees_at is not None:
                if frees_at > now:
                    continue
                del _quarantined[slot]
            _leased[slot] = sticky
            return Exit(country, sticky)
    raise RuntimeError("no free sticky exit slot")


def release_exit(exit: Exit, *, burned: bool = False) -> None:
    """Give a leased exit back; ``burned`` keeps its IP out of new leases for a while.

    Idempotent, and a no-op for the rotating gateway.
    """
    if exit.sticky is None:
        return
    slot = get_active_provider().sticky_slot(exit.sticky)
    with _lease_lock:
        if _leased.get(slot) == exit.sticky:
            del _leased[slot]
        if burned:
            now = time.monotonic()
            if len(_quarantined) > 4096:  # drop expired ones before growing further
                for key in [k for k, t in _quarantined.items() if t <= now]:
                    del _quarantined[key]
            _quarantined[slot] = now + BURN_QUARANTINE_S


class _Conn:
    """One curl session and the requests in flight on it."""

    def __init__(self, max_clients: int) -> None:
        global _live_sessions
        self.session: AsyncSession = http.open_session(max_clients=max_clients)
        self.inflight = 0
        self.retired = False
        self.closed = False
        _live_sessions += 1

    async def close(self) -> None:
        global _live_sessions
        if self.closed:
            return
        self.closed = True
        _live_sessions -= 1
        with suppress(Exception):  # best-effort teardown
            await self.session.close()


class SessionHolder:
    """One job's keep-alive session on one exit, replaced whole on rotate or burn.

    Opened lazily on the first request. ``rotate`` retires the session (requests
    already in flight on it finish there), takes a new exit and opens a new session
    on the next request. Requests from several tasks may share a holder; at most
    ``max_streams`` run at once on it. Once closed it never opens a session again.
    """

    def __init__(
        self,
        plugin: str,
        exit: Exit,
        *,
        max_uses: int | None = None,
        max_streams: int = 8,
    ) -> None:
        self.plugin = plugin
        self.exit = exit
        self.uses = 0
        self.burned = False
        self.rotations = 0
        self.max_uses = max_uses
        self._owns_lease = False  # only exits this holder leased are its to release
        self._proxy = exit.proxy_url()
        self._max_streams = max(1, max_streams)
        self._streams = asyncio.Semaphore(self._max_streams)
        self._conn: _Conn | None = None
        self._retired: set[_Conn] = set()
        self._active = 0  # requests inside request(), waiting for a stream included
        self._closed = False

    @property
    def proxy(self) -> str | None:
        """This exit's proxy URL, for a browser or Scrapling call that must share it."""
        return self._proxy

    async def request(
        self, method: str, url: str, *, stage: str, **kw: Any
    ) -> http.RawResponse:
        """:func:`proprietary.scraping.http.request` over this holder's session.

        Takes every keyword of ``http.request`` except ``plugin``, ``proxy`` and
        ``session``, which the holder supplies. On a closed holder it raises
        ``TransportError`` (kind ``SessionClosed``), which a rotation loop treats
        as a dead exit.
        """
        self._active += 1
        try:
            async with self._streams:
                if self.burned:
                    await self.rotate("burned")
                elif self.max_uses is not None and self.uses >= self.max_uses:
                    await self.rotate("max_uses")
                # Checked after the rotate's await: a session opened now would leak.
                if self._closed:
                    raise http.TransportError("SessionClosed", 0, 0.0, "holder closed")
                if self._conn is None:
                    # Enough curl handles that a request never waits for one here.
                    self._conn = _Conn(max(10, self._max_streams))
                # Taken together: a rotate while this runs must not mix the two.
                conn, proxy = self._conn, self._proxy
                self.uses += 1
                conn.inflight += 1
                try:
                    return await http.request(
                        method,
                        url,
                        plugin=self.plugin,
                        stage=stage,
                        proxy=proxy,
                        session=conn.session,
                        **kw,
                    )
                finally:
                    conn.inflight -= 1
                    if conn.retired and conn.inflight == 0:
                        self._retired.discard(conn)
                        await conn.close()
        finally:
            self._active -= 1

    async def rotate(
        self, reason: str, *, country: str | None = None, seen: int | None = None
    ) -> None:
        """Drop this exit and its session; the next request goes out on a new exit.

        A sticky exit is replaced by a new leased one and the old IP is quarantined;
        the gateway is redrawn by the new connection. ``country`` moves the exit.
        ``seen`` is :attr:`rotations` as read before the refused request: when
        another task sharing the holder has rotated since, this call does nothing,
        so one refused exit costs one rotation however many tasks saw it refused.
        A closed holder does not rotate.
        """
        if self._closed or (seen is not None and seen != self.rotations):
            return
        # Swap before the first await, so a task sharing the holder never sees a
        # half-rotated one.
        old, conn = self.exit, self._detach()
        if self._owns_lease:
            release_exit(old, burned=True)
        new_country = country if country is not None else old.country
        if old.sticky is not None:
            self.exit = lease_exit(self.plugin, new_country)
            self._owns_lease = True
        else:
            self.exit = Exit(new_country)
            self._owns_lease = False
        self._proxy = self.exit.proxy_url()
        self.rotations += 1
        self.uses = 0
        self.burned = False
        logger.info(
            "[%s] rotated session (#%d, reason=%s, country=%s)",
            self.plugin,
            self.rotations,
            reason,
            self.exit.country or "-",
        )
        if conn is not None:
            await conn.close()

    def burn(self, reason: str) -> None:
        """Mark this exit refused: never kept idle, rotated before the next request."""
        if not self.burned:
            logger.info("[%s] burned session (reason=%s)", self.plugin, reason)
        self.burned = True

    async def close(self) -> None:
        """Close this holder's session and release its own lease; idempotent.

        A session with requests still in flight is left to its last request to
        close, as after ``rotate``: closing it under them would hand back status 0
        or a truncated body (curl_cffi resolves them, it does not fail them).
        Their curl timeout bounds the wait. Later requests raise.
        """
        self._closed = True
        conn = self._detach()
        if self._owns_lease:
            release_exit(self.exit, burned=self.burned)
            self._owns_lease = False
        if conn is not None:
            await conn.close()

    def _detach(self) -> _Conn | None:
        """Take the session out of service; returns it when nothing runs on it."""
        conn, self._conn = self._conn, None
        if conn is None:
            return None
        conn.retired = True
        if conn.inflight:
            self._retired.add(conn)  # its last request closes it
            return None
        return conn


_current: ContextVar[SessionHolder | None] = ContextVar(
    "scraping_session_holder", default=None
)


@contextmanager
def bind(h: SessionHolder) -> Iterator[None]:
    """Make ``h`` this task's :func:`current` holder for the block."""
    token = _current.set(h)
    try:
        yield
    finally:
        _current.reset(token)


def current() -> SessionHolder | None:
    """The holder bound in this task (or inherited by tasks it started), if any."""
    return _current.get()


@asynccontextmanager
async def holder(
    plugin: str,
    exit: Exit | None = None,
    *,
    max_uses: int | None = None,
    max_streams: int = 8,
    keep_idle: bool = False,
) -> AsyncIterator[SessionHolder]:
    """One job's :class:`SessionHolder`, closed (or kept idle) when the block ends.

    ``exit=None`` is the rotating gateway in the configured country. An exit the
    caller leased stays the caller's to release; one leased by ``rotate`` is
    released here. With ``keep_idle`` (gateway exits only) the block may get a warm
    session another call of the same plugin left, and leaves its own for the next
    call when it ends normally, unburned and still on the exit it asked for.
    """
    wanted = exit or Exit()
    h = _take_idle(plugin, wanted) if keep_idle else None
    if h is None:
        h = SessionHolder(plugin, wanted, max_uses=max_uses, max_streams=max_streams)
    else:
        h.max_uses = max_uses  # `uses` carries on: it counts requests on this exit
    try:
        yield h
    except BaseException:
        await h.close()
        raise
    if keep_idle and _keepable(h, wanted):
        _put_idle(h)
    else:
        await h.close()


@asynccontextmanager
async def bound(
    plugin: str, exit: Exit | None = None, **kw: Any
) -> AsyncIterator[SessionHolder]:
    """:func:`holder` and :func:`bind` in one, e.g. as ``ordered_map``'s worker_context."""
    async with holder(plugin, exit, **kw) as h:
        with bind(h):
            yield h


def live_sessions() -> int:
    """Curl sessions holders have open right now, idle ones included."""
    return _live_sessions


# Idle sessions between calls: (plugin, exit) -> [(expires_at, holder, loop)], LIFO.
_idle: dict[tuple[str, Exit], list[tuple[float, SessionHolder, Any]]] = {}
_reaper: asyncio.Task | None = None


def _keepable(h: SessionHolder, wanted: Exit) -> bool:
    return (
        Config.MAX_IDLE_SESSIONS > 0
        # A sticky exit's lease belongs to its job; keeping it would outlive that.
        and wanted.sticky is None
        and not h.burned
        and h.exit == wanted
        and h._conn is not None
        and not h._retired
        # A request still running (or waiting for a stream) belongs to this call.
        and h._active == 0
    )


def _take_idle(plugin: str, wanted: Exit) -> SessionHolder | None:
    key = (plugin, wanted)
    entries = _idle.get(key, [])
    loop = asyncio.get_running_loop()
    now = time.monotonic()
    found = None
    while entries and found is None:
        expires_at, h, h_loop = entries.pop()
        if h_loop is loop and expires_at > now:
            found = h
        else:
            _close_later(h, h_loop)
    if not entries:
        _idle.pop(key, None)
    return found


def _put_idle(h: SessionHolder) -> None:
    global _reaper
    at_shutdown(close_idle)
    if h._conn is not None:
        h._conn.session.cookies.clear()  # the next call starts without this one's
    loop = asyncio.get_running_loop()
    _idle.setdefault((h.plugin, h.exit), []).append(
        (time.monotonic() + IDLE_TTL_S, h, loop)
    )
    while sum(len(v) for v in _idle.values()) > Config.MAX_IDLE_SESSIONS:
        _evict_one()
    if _reaper is None or _reaper.done() or _reaper.get_loop() is not loop:
        _reaper = loop.create_task(_reap())


def _evict_one() -> None:
    """Close the oldest idle session of the plugin keeping the most.

    So one plugin's wide fan-out cannot push every other plugin's warm sessions out.
    """
    counts = Counter(k[0] for k, v in _idle.items() for _ in v)
    most = max(counts.values())
    key, index = min(
        (
            (k, i)
            for k, v in _idle.items()
            if counts[k[0]] == most
            for i in range(len(v))
        ),
        key=lambda ki: _idle[ki[0]][ki[1]][0],
    )
    _, h, h_loop = _idle[key].pop(index)
    if not _idle[key]:
        del _idle[key]
    _close_later(h, h_loop)


_closing: set[asyncio.Task] = set()


def _close_later(h: SessionHolder, h_loop: Any) -> None:
    # A session made on another loop (only in tests) cannot be closed from this one.
    if h_loop is asyncio.get_running_loop():
        task = h_loop.create_task(h.close())
        _closing.add(task)
        task.add_done_callback(_closing.discard)


async def _reap() -> None:
    """Close idle sessions as their TTL runs out; stops when none are left."""
    while True:
        soonest = min((t for v in _idle.values() for t, _, _ in v), default=None)
        if soonest is None:
            return
        await asyncio.sleep(max(0.0, soonest - time.monotonic()) + 0.05)
        now = time.monotonic()
        expired: list[SessionHolder] = []
        for key in list(_idle):
            keep = [e for e in _idle[key] if e[0] > now]
            expired += [e[1] for e in _idle[key] if e[0] <= now]
            if keep:
                _idle[key] = keep
            else:
                del _idle[key]
        for h in expired:
            await h.close()


async def close_idle() -> None:
    """Close every idle session; registered with lifecycle.at_shutdown on first use."""
    global _reaper
    loop = asyncio.get_running_loop()
    if _reaper is not None and not _reaper.done() and _reaper.get_loop() is loop:
        _reaper.cancel()
        with suppress(asyncio.CancelledError):
            await _reaper
    _reaper = None
    entries = [e for v in _idle.values() for e in v]
    _idle.clear()
    for _, h, h_loop in entries:
        if h_loop is loop:
            await h.close()
    closing = [t for t in _closing if t.get_loop() is loop]
    if closing:
        await asyncio.gather(*closing, return_exceptions=True)
