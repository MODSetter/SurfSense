"""One shared, kept Chromium pool for every browser scraper, on the browser loop.

Before this, most browser plugins launched a Chromium per call or per page and paid
the driver (0.3 s), the launch (0.1-0.9 s here, about 5 s in prod) and the close
(up to 9.5 s) every time, plus 350 MB per concurrent call. Here one browser per
launch profile is started once and kept; each page gets a fresh proxied context on
it, or a kept context for sites whose clearance is worth keeping (Indeed).

Generalised from google_search/fetch.py, whose rules encode production incidents:
pages are gated by our own semaphore (scrapling's page pool raised 'Maximum page
limit' under overlap), and a browser is never closed under a sibling's page: a
dropped browser closes when its last page finishes.

Everything here runs on the browser loop (proprietary.scraping.browser_loop): enter
`page()` inside a coroutine handed to `run()`, never in to_thread, so cancelling
the caller cancels the page and closes only its own context.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable, Collection, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from scrapling.engines.constants import EXTRA_RESOURCES
from scrapling.fetchers import AsyncStealthySession, ProxyRotator

from proprietary.scraping import lifecycle, sessions
from proprietary.scraping.browser_loop import get_browser_loop, in_browser_loop

logger = logging.getLogger(__name__)


def _env_number(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


# Read at import. Pages are the throughput lever: one Chromium holds several
# text-only contexts, so raise pages before browsers.
_MAX_BROWSERS = int(_env_number("SCRAPING_MAX_BROWSERS", 3))
_MAX_PAGES = int(_env_number("SCRAPING_MAX_BROWSER_PAGES", 6))
# 0 turns kept contexts off: page(kept=...) then gets a fresh context.
_MAX_KEPT = int(_env_number("SCRAPING_MAX_KEPT_CONTEXTS", 4))
# Idle seconds before a browser closes; 0 closes it as soon as no page is open.
_BROWSER_IDLE_S = _env_number("SCRAPING_BROWSER_IDLE_S", 600)
_DEFAULT_BROWSER_IDLE_S = _env_number("SCRAPING_DEFAULT_BROWSER_IDLE_S", 1800)

_PLUGIN_PAGES = 4  # per plugin unless set_plugin_cap says otherwise
_KEPT_PAGES = 3  # pages open at once on one kept context
_KEPT_IDLE_S = 600.0
_KEPT_MAX_AGE_S = 1200.0
_KEPT_MAX_NAVIGATIONS = 60
_REAP_EVERY_S = 30.0
# A new_context or new_page that takes this long means a wedged browser, not a slow
# site.
_CONTEXT_TIMEOUT_S = 20.0
# A browser close plus its driver stop must fit in lifecycle.CLOSE_SECONDS (15 s),
# or the shutdown cancel skips the driver stop.
_CLOSE_TIMEOUT_S = 6.0

# Rotator mode only makes scrapling's start() launch a plain browser instead of a
# persistent context; the pool never calls fetch(), so this is never dialled.
_UNUSED_ROTATOR_PROXY = "http://127.0.0.1:9"

# Google's mobile layout (google_search/fetch.py): a Firefox-on-Android UA is what
# gets it served without the wall. UA and viewport are context options, so a
# mobile page shares the desktop browser.
_MOBILE_CONTEXT = {
    "user_agent": "Mozilla/5.0 (Android 14; Mobile; rv:132.0) Gecko/132.0 Firefox/132.0",
    "viewport": {"width": 412, "height": 915},
}

# A proxy URL, or a zero-arg callable called only when a context is built. A
# callable may return a leased sessions.Exit; the pool gives it back (quarantined
# when burned) once the context it built closes.
ProxyArg = str | Callable[[], str | sessions.Exit | None] | None

_clock = time.monotonic
_plugin_caps: dict[str, int] = {}


@dataclass(frozen=True)
class LaunchProfile:
    """How a browser is launched; every distinct launch profile is one Chromium.

    `mobile` is applied per context (UA and viewport), so it never adds a browser.
    `locale` is a launch flag in scrapling 0.4.15 (workers follow it too).
    """

    headless: bool = True
    mobile: bool = False
    block_webrtc: bool = False
    hide_canvas: bool = False
    dns_over_https: bool = False
    locale: str | None = None

    def launch_key(self) -> LaunchProfile:
        """The browser this profile runs on: the same profile without `mobile`."""
        return replace(self, mobile=False)


# The headless desktop browser most plugins share; it stays up longest when idle.
DEFAULT_PROFILE = LaunchProfile()


@dataclass(eq=False)
class PooledPage:
    """A page lent by the pool; `burn()` it when the site blocked it."""

    page: Any
    context: Any
    plugin: str
    kept: str | None  # the kept-context key, None on a fresh context
    queue_ms: float  # waiting for a page slot
    launch_ms: float  # 0 when the browser was already up
    context_ms: float  # 0 when a kept context was reused
    proxy: str | None = field(default=None, repr=False)
    burned: str | None = None
    _session: Any = field(default=None, repr=False)

    @property
    def warm_browser(self) -> bool:
        return self.launch_ms == 0

    @property
    def warm_context(self) -> bool:
        return self.context_ms == 0

    def burn(self, reason: str) -> None:
        """Mark this page's context blocked: a kept one is never lent again."""
        if self.burned is None:
            self.burned = reason


class _Browser:
    def __init__(self, key: LaunchProfile, session: Any) -> None:
        self.key = key
        self.session = session
        self.pages = 0
        self.last_used = _clock()
        self.doomed = False

    def connected(self) -> bool:
        browser = self.session.browser
        return browser is not None and browser.is_connected()


class _Kept:
    def __init__(
        self,
        key: str,
        browser: _Browser,
        context: Any,
        proxy: str | None,
        lease: sessions.Exit | None,
        profile: LaunchProfile,
    ) -> None:
        self.key = key
        self.browser = browser
        self.context = context
        self.proxy = proxy
        self.lease = lease
        self.profile = profile
        self.created = self.last_used = _clock()
        self.navigations = 0
        self.pages = 0
        self.retired = False
        self.burned = False
        self.closing = False  # its close is spawned; never spawn a second one


class _Pool:
    """All state lives on the browser loop; nothing here is touched from elsewhere."""

    def __init__(self) -> None:
        self.browsers: dict[LaunchProfile, _Browser] = {}
        self.draining: set[_Browser] = set()
        self.kept: OrderedDict[str, _Kept] = OrderedDict()
        self.pages = asyncio.Semaphore(max(1, _MAX_PAGES))
        self.plugin_gates: dict[str, asyncio.Semaphore] = {}
        self.kept_gates: dict[str, asyncio.Semaphore] = {}
        self.kept_locks: dict[str, asyncio.Lock] = {}
        self.launch_lock = asyncio.Lock()
        self.tasks: set[asyncio.Task] = set()
        self.reaper = asyncio.get_running_loop().create_task(self._reap_forever())

    # -- gates -------------------------------------------------------------

    def plugin_gate(self, plugin: str) -> asyncio.Semaphore:
        gate = self.plugin_gates.get(plugin)
        if gate is None:
            cap = _plugin_caps.get(plugin, _PLUGIN_PAGES)
            gate = self.plugin_gates[plugin] = asyncio.Semaphore(max(1, cap))
        return gate

    def kept_gate(self, key: str) -> asyncio.Semaphore:
        gate = self.kept_gates.get(key)
        if gate is None:
            gate = self.kept_gates[key] = asyncio.Semaphore(_KEPT_PAGES)
        return gate

    # -- browsers ----------------------------------------------------------

    async def claim_browser(self, profile: LaunchProfile) -> tuple[_Browser, float]:
        """A live browser for `profile` with one page claimed on it, and launch ms.

        Launch ms includes waiting for another caller's launch: that is cold-start
        cost for this call too.
        """
        key = profile.launch_key()
        b = self.browsers.get(key)
        if b is None or not b.connected():
            started = time.perf_counter()
            # One launch at a time, so the browser cap holds under a burst.
            async with self.launch_lock:
                b = self.browsers.get(key)
                if b is not None and not b.connected():
                    self.doom(b, "disconnected")
                    b = None
                if b is None:
                    b = await self._launch(key)
                b.pages += 1
                return b, (time.perf_counter() - started) * 1000
        b.pages += 1
        return b, 0.0

    async def _launch(self, key: LaunchProfile) -> _Browser:
        while len(self.browsers) >= max(1, _MAX_BROWSERS):
            # Least recently used first: idle ones before busy ones, and ones
            # without a kept clearance before those holding one.
            lru = min(
                self.browsers.values(),
                key=lambda x: (x.pages > 0, self.holds_kept(x), x.last_used),
            )
            self.doom(lru, "browser cap")
        session = _new_session(key)
        try:
            await session.start()
        except BaseException:
            # scrapling stops its driver on errors but not on a cancel (a Stop
            # during the launch), which would orphan a node process.
            self.spawn(_close_session(session))
            raise
        b = _Browser(key, session)
        session.browser.on("disconnected", lambda *_: self.doom(b, "disconnected"))
        self.browsers[key] = b
        logger.info(
            "[scraping][browser] launched %s (browsers=%d)", key, len(self.browsers)
        )
        return b

    def doom(self, b: _Browser, reason: str) -> None:
        """Stop lending `b`; it closes now if idle, else when its last page ends."""
        if b.doomed:
            return
        b.doomed = True
        if self.browsers.get(b.key) is b:
            del self.browsers[b.key]
        for k in [k for k in self.kept.values() if k.browser is b]:
            self.retire(k, reason)
        logger.info("[scraping][browser] dropping %s: %s", b.key, reason)
        self.draining.add(b)
        if b.pages == 0:
            self.spawn(self._close_browser(b))

    async def _close_browser(self, b: _Browser) -> None:
        if b not in self.draining:  # another close already took it
            return
        self.draining.discard(b)
        await _close_session(b.session)

    # -- contexts ----------------------------------------------------------

    async def new_context(
        self,
        b: _Browser,
        profile: LaunchProfile,
        proxy: str | None,
        context_options: Mapping[str, Any] | None,
    ) -> Any:
        session = b.session
        options = session._build_context_with_proxy(proxy)
        if profile.mobile:
            options.update(_MOBILE_CONTEXT)
        if context_options:
            options.update(context_options)
        context = None
        try:
            async with asyncio.timeout(_CONTEXT_TIMEOUT_S):
                context = await session.browser.new_context(**options)
                return await session._initialize_context(session._config, context)
        except BaseException as error:
            # A cancel or a failed init would leave the context open on a browser
            # that may live for hours.
            if context is not None:
                self.spawn(_close_quietly(context))
            if isinstance(error, TimeoutError):
                self.doom(b, "new_context timed out")
            elif not b.connected():
                self.doom(b, "disconnected")
            raise

    async def new_page(self, b: _Browser, context: Any) -> Any:
        try:
            async with asyncio.timeout(_CONTEXT_TIMEOUT_S):
                return await context.new_page()
        except TimeoutError:
            self.doom(b, "new_page timed out")
            raise

    def kept_stale(self, k: _Kept, profile: LaunchProfile | None = None) -> str | None:
        now = _clock()
        if k.retired or k.browser.doomed or not k.browser.connected():
            return "browser gone"
        if profile is not None and profile != k.profile:
            return "profile changed"
        if now - k.created >= _KEPT_MAX_AGE_S:
            return "max age"
        if k.pages == 0 and now - k.last_used >= _KEPT_IDLE_S:
            return "idle"
        if k.navigations >= _KEPT_MAX_NAVIGATIONS:
            return "max navigations"
        return None

    async def claim_kept(
        self,
        key: str,
        profile: LaunchProfile,
        proxy: ProxyArg,
        context_options: Mapping[str, Any] | None,
    ) -> tuple[_Kept, float, float]:
        """The kept context for `key` with one page claimed, plus launch and context ms."""
        lock = self.kept_locks.setdefault(key, asyncio.Lock())
        async with lock:  # two first calls for one key build one context
            k = self.kept.get(key)
            if k is not None and (reason := self.kept_stale(k, profile)):
                self.retire(k, reason)
                k = None
            if k is not None:
                self.kept.move_to_end(key)
                k.pages += 1
                k.browser.pages += 1
                return k, 0.0, 0.0
            b, launch_ms = await self.claim_browser(profile)
            started = time.perf_counter()
            lease = None
            try:
                exit_url, lease = _take_exit(proxy)
                context = await self.new_context(b, profile, exit_url, context_options)
            except BaseException:
                self.release_browser(b)
                if lease is not None:
                    _release_lease(lease, burned=False)
                raise
            k = _Kept(key, b, context, exit_url, lease, profile)
            k.pages = 1
            self.kept[key] = k
            while len(self.kept) > max(1, _MAX_KEPT):
                self.retire(next(iter(self.kept.values())), "kept cap")
            return k, launch_ms, (time.perf_counter() - started) * 1000

    def retire(self, k: _Kept, reason: str) -> None:
        """Never lend `k` again; its context closes once its open pages end."""
        if k.retired:
            return
        k.retired = True
        if self.kept.get(k.key) is k:
            del self.kept[k.key]
        logger.info("[scraping][browser] retiring kept context %s: %s", k.key, reason)
        self.close_if_done(k)

    def close_if_done(self, k: _Kept) -> None:
        """Close a retired kept context once its last page ends, exactly once."""
        if k.retired and k.pages == 0 and not k.closing:
            k.closing = True
            self.spawn(_close_quietly(k.context, k.lease, burned=k.burned))

    # -- release -----------------------------------------------------------

    def release_browser(self, b: _Browser) -> None:
        b.pages -= 1
        b.last_used = _clock()
        if b.pages:
            return
        if b.doomed:
            if b in self.draining:
                self.spawn(self._close_browser(b))
        elif not b.connected():
            self.doom(b, "disconnected")
        elif _idle_limit(b.key) <= 0 and not self.holds_kept(b):
            self.doom(b, "idle")

    def release_kept(self, k: _Kept, burned: str | None) -> None:
        k.pages -= 1
        k.last_used = _clock()
        if burned:
            k.burned = True  # even when a sibling retired it first: quarantine the IP
            self.retire(k, f"burned: {burned}")
        elif k.navigations >= _KEPT_MAX_NAVIGATIONS:
            self.retire(k, "max navigations")
        # Whichever way it was retired, the last page out closes it.
        self.close_if_done(k)

    # -- housekeeping ------------------------------------------------------

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def reap(self) -> None:
        """Retire stale kept contexts and close browsers idle past their limit."""
        for k in list(self.kept.values()):
            if reason := self.kept_stale(k):
                self.retire(k, reason)
        now = _clock()
        for b in list(self.browsers.values()):
            idle = b.pages == 0 and now - b.last_used >= _idle_limit(b.key)
            if idle and not self.holds_kept(b):
                self.doom(b, "idle")

    def holds_kept(self, b: _Browser) -> bool:
        """A live kept context keeps its browser up: closing it loses the clearance."""
        return any(k.browser is b for k in self.kept.values())

    async def _reap_forever(self) -> None:
        while True:
            await asyncio.sleep(_REAP_EVERY_S)
            try:
                self.reap()
            except Exception:
                logger.exception("[scraping][browser] reaping failed")

    async def close(self) -> None:
        self.reaper.cancel()
        for b in list(self.browsers.values()):
            self.doom(b, "shutdown")
        # Busy browsers too: at shutdown nobody waits for their pages.
        for b in list(self.draining):
            self.spawn(self._close_browser(b))
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)

    def stats(self) -> dict[str, int]:
        return {
            "browsers": len(self.browsers),
            "draining": len(self.draining),
            "pages": sum(b.pages for b in (*self.browsers.values(), *self.draining)),
            "kept": len(self.kept),
        }


def _idle_limit(key: LaunchProfile) -> float:
    return _DEFAULT_BROWSER_IDLE_S if key == DEFAULT_PROFILE else _BROWSER_IDLE_S


def _new_session(profile: LaunchProfile) -> Any:
    """An unstarted stealth session that launches a plain browser for our contexts."""
    kwargs: dict[str, Any] = {
        "headless": profile.headless,
        "block_webrtc": profile.block_webrtc,
        "hide_canvas": profile.hide_canvas,
        "dns_over_https": profile.dns_over_https,
        "proxy_rotator": ProxyRotator([_UNUSED_ROTATOR_PROXY]),
    }
    if profile.locale:
        kwargs["locale"] = profile.locale
    return AsyncStealthySession(**kwargs)


async def _close_quietly(
    target: Any, lease: sessions.Exit | None = None, *, burned: bool = False
) -> None:
    """Close `target` (if any), then give back the exit its context ran on."""
    if target is not None:
        with contextlib.suppress(Exception):
            async with asyncio.timeout(_CLOSE_TIMEOUT_S):
                await target.close()
    if lease is not None:
        _release_lease(lease, burned=burned)


def _take_exit(proxy: ProxyArg) -> tuple[str | None, sessions.Exit | None]:
    """The proxy URL for a new context, and the lease to give back when it closes."""
    value = proxy() if callable(proxy) else proxy
    if not isinstance(value, sessions.Exit):
        return value, None
    try:
        return value.proxy_url(), value
    except BaseException:
        _release_lease(value, burned=False)
        raise


def _release_lease(lease: sessions.Exit, *, burned: bool) -> None:
    try:
        sessions.release_exit(lease, burned=burned)
    except Exception:
        logger.exception("[scraping][browser] giving back a sticky exit failed")


async def _close_session(session: Any) -> None:
    """Close a browser and always stop its driver, or a node process is orphaned."""
    await _close_quietly(session)
    # scrapling's close skips the driver stop when the browser close raised.
    if getattr(session, "playwright", None) is not None:
        with contextlib.suppress(Exception):
            async with asyncio.timeout(_CLOSE_TIMEOUT_S):
                await session.playwright.stop()
        session.playwright = None


def _route_handler(resource_types: frozenset[str], url_parts: tuple[str, ...]):
    async def handle(route) -> None:
        request = route.request
        with contextlib.suppress(Exception):  # the page closed under the request
            if request.resource_type in resource_types or any(
                part in request.url for part in url_parts
            ):
                await route.abort()
            else:
                await route.continue_()

    return handle


_pool: _Pool | None = None


def _get_pool() -> _Pool:
    global _pool
    if _pool is None:
        _pool = _Pool()
        lifecycle.at_shutdown(close_all)
    return _pool


def _on_browser_loop() -> bool:
    try:
        return asyncio.get_running_loop() is get_browser_loop()
    except RuntimeError:
        return False


def set_plugin_cap(plugin: str, pages: int) -> None:
    """Cap `plugin`'s open pages (default 4); call it at import, before any page."""
    _plugin_caps[plugin] = pages


@contextlib.asynccontextmanager
async def page(
    plugin: str,
    profile: LaunchProfile = DEFAULT_PROFILE,
    *,
    proxy: ProxyArg = None,
    kept: str | None = None,
    disable_resources: bool | Collection[str] = True,
    block_url_patterns: Collection[str] = (),
    extra_headers: Mapping[str, str] | None = None,
    context_options: Mapping[str, Any] | None = None,
    timeout_ms: int = 15000,
) -> AsyncIterator[PooledPage]:
    """Lend a page on the shared browser for `profile`; enter it on the browser loop.

    A fresh context on `proxy` per call, closed on exit; or, with `kept`, the kept
    context of that key (built on the first call's proxy and reused until it idles,
    ages, navigates too often or is burned). `proxy` may be a callable, called only
    when a context is built, so a sticky lease is taken only when needed; a leased
    `sessions.Exit` it returns is given back when that context closes.

    An exception (not a cancel) leaving the block burns a kept context, as the old
    per-call fetchers rotated to a new exit on any error.
    """
    if not _on_browser_loop():
        raise RuntimeError("browser_pool.page() runs on the browser loop: use run()")
    pool = _get_pool()
    use_kept = bool(kept) and _MAX_KEPT > 0
    started = time.perf_counter()
    async with contextlib.AsyncExitStack() as gates:
        await gates.enter_async_context(pool.plugin_gate(plugin))
        if use_kept:
            await gates.enter_async_context(pool.kept_gate(kept))
        await gates.enter_async_context(pool.pages)
        queue_ms = (time.perf_counter() - started) * 1000

        k: _Kept | None = None
        context: Any = None
        lease: sessions.Exit | None = None  # a fresh context's exit, given back on exit
        if use_kept:
            k, launch_ms, context_ms = await pool.claim_kept(
                kept, profile, proxy, context_options
            )
            b, context, exit_url = k.browser, k.context, k.proxy
        else:
            b, launch_ms = await pool.claim_browser(profile)
        pooled: PooledPage | None = None
        lent = False
        error: Exception | None = None
        held = time.perf_counter()
        try:
            if k is None:
                started = time.perf_counter()
                exit_url, lease = _take_exit(proxy)
                context = await pool.new_context(b, profile, exit_url, context_options)
                context_ms = (time.perf_counter() - started) * 1000
            pooled = PooledPage(
                page=None,
                context=context,
                plugin=plugin,
                kept=kept if k is not None else None,
                queue_ms=queue_ms,
                launch_ms=launch_ms,
                context_ms=context_ms,
                proxy=exit_url,
                _session=b.session,
            )
            pooled.page = await pool.new_page(b, context)
            await _set_up(
                pooled.page,
                k,
                disable_resources,
                block_url_patterns,
                extra_headers,
                timeout_ms,
            )
            lent = True
            yield pooled
        except Exception as e:
            error = e
            raise
        finally:
            # Bookkeeping first and synchronously, so a second cancel can't skip it;
            # the close runs as its own task and finishes even if we are cancelled.
            burned = pooled.burned if pooled is not None else None
            if burned is None and error is not None and k is not None:
                # A dead exit, a crashed context or a failed solve: the next call
                # must not get the same exit and clearance.
                stage = "error" if lent else "page setup failed"
                burned = f"{stage}: {type(error).__name__}"
            if k is not None:
                closing = pooled.page if pooled is not None else None
                pool.release_kept(k, burned)
            else:
                closing = context
            close_task = (
                pool.spawn(_close_quietly(closing, lease, burned=burned is not None))
                if closing is not None or lease is not None
                else None
            )
            pool.release_browser(b)
            logger.info(
                "[scraping][browser][perf] plugin=%s kept=%s queue_ms=%.0f launch_ms=%.0f"
                " context_ms=%.0f held_ms=%.0f burned=%s",
                plugin,
                kept if k is not None else None,
                queue_ms,
                launch_ms,
                context_ms if pooled is not None else -1,
                (time.perf_counter() - held) * 1000,
                burned,
            )
            if close_task is not None:
                await asyncio.shield(close_task)


async def _set_up(
    pg: Any,
    k: _Kept | None,
    disable_resources: bool | Collection[str],
    block_url_patterns: Collection[str],
    extra_headers: Mapping[str, str] | None,
    timeout_ms: int,
) -> None:
    pg.set_default_navigation_timeout(timeout_ms)
    pg.set_default_timeout(timeout_ms)
    if extra_headers:
        await pg.set_extra_http_headers(dict(extra_headers))
    if disable_resources is True:
        types = frozenset(EXTRA_RESOURCES)
    else:
        types = frozenset(disable_resources or ())
    parts = tuple(block_url_patterns)
    # Routing turns Chromium's HTTP cache off, so only route when something drops.
    if types or parts:
        await pg.route("**/*", _route_handler(types, parts))
    if k is not None:

        def count(frame) -> None:
            if frame.parent_frame is None:
                k.navigations += 1

        pg.on("framenavigated", count)


async def _call[T](fn: Callable[[], Awaitable[T]]) -> T:
    return await fn()


async def run[T](fn: Callable[[], Awaitable[T]]) -> T:
    """Run `fn()` on the browser loop and await it here; cancelling us cancels it."""
    if _on_browser_loop():
        return await fn()
    return await in_browser_loop(_call(fn))


async def warm(profile: LaunchProfile = DEFAULT_PROFILE) -> None:
    """Launch `profile`'s browser now, with no page and no proxy (e.g. at startup)."""

    async def launch() -> None:
        pool = _get_pool()
        b, _ = await pool.claim_browser(profile)
        pool.release_browser(b)

    await run(launch)


async def close_all() -> None:
    """Close every browser and context (host shutdown); the next page() starts afresh."""
    if _pool is None:
        return

    async def close_on_loop() -> None:
        global _pool
        pool, _pool = _pool, None
        if pool is not None:
            await pool.close()

    await run(close_on_loop)


async def stats() -> dict[str, int]:
    """Live browsers, draining browsers, open pages and kept contexts."""
    if _pool is None:
        return dict(_NO_STATS)
    return await run(_stats_on_loop)


_NO_STATS = {"browsers": 0, "draining": 0, "pages": 0, "kept": 0}


async def _stats_on_loop() -> dict[str, int]:
    return _pool.stats() if _pool is not None else dict(_NO_STATS)
