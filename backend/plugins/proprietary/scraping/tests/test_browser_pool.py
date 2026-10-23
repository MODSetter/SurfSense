"""Unit tests for the shared browser pool.

Offline: scrapling's session is replaced by fakes, so no browser starts and no
network is touched. The pool still runs on the real browser loop through run(),
so the cross-loop path and its cancellation are the ones production uses. The
contract tests at the end pin the scrapling internals the pool depends on.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from importlib.metadata import version
from typing import ClassVar

import pytest

from proprietary.scraping import browser_pool as bp
from proprietary.scraping import lifecycle, sessions
from proprietary.scraping.browser_loop import get_browser_loop


class FakeRoute:
    def __init__(self, url: str, resource_type: str) -> None:
        self.request = type("Req", (), {"url": url, "resource_type": resource_type})
        self.outcome = ""

    async def abort(self) -> None:
        self.outcome = "abort"

    async def continue_(self) -> None:
        self.outcome = "continue"


class FakeFrame:
    parent_frame = None


class FakePage:
    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.closed = False
        self.timeouts: list[int] = []
        self.headers: dict = {}
        self.routes: list = []
        self.listeners: dict = {}

    def set_default_navigation_timeout(self, ms: int) -> None:
        self.timeouts.append(ms)

    def set_default_timeout(self, ms: int) -> None:
        self.timeouts.append(ms)

    async def set_extra_http_headers(self, headers: dict) -> None:
        self.headers = headers

    async def route(self, pattern: str, handler) -> None:
        self.routes.append((pattern, handler))

    def on(self, event: str, callback) -> None:
        self.listeners.setdefault(event, []).append(callback)

    def navigate(self) -> None:
        for callback in self.listeners.get("framenavigated", []):
            callback(FakeFrame())

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, browser: FakeBrowser, options: dict) -> None:
        self.browser = browser
        self.options = options
        self.closed = False
        self.closes = 0
        self.broken = False  # crashed under a live browser: new_page fails
        self.pages: list[FakePage] = []

    async def new_page(self) -> FakePage:
        if self.broken:
            raise RuntimeError("Target page, context or browser has been closed")
        if self.browser.page_hang:
            await asyncio.sleep(3600)
        page = FakePage(self)
        self.pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True
        self.closes += 1


class FakeBrowser:
    def __init__(self) -> None:
        self.connected = True
        self.contexts: list[FakeContext] = []
        self.callbacks: list = []
        self.hang = False
        self.page_hang = False

    def on(self, event: str, callback) -> None:
        assert event == "disconnected"
        self.callbacks.append(callback)

    def is_connected(self) -> bool:
        return self.connected

    async def new_context(self, **options) -> FakeContext:
        if self.hang:
            await asyncio.sleep(3600)
        context = FakeContext(self, options)
        self.contexts.append(context)
        return context

    def disconnect(self) -> None:
        self.connected = False
        for callback in self.callbacks:
            callback(self)


class FakeDriver:
    def __init__(self) -> None:
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakeSession:
    made: ClassVar[list[FakeSession]] = []

    def __init__(self, profile: bp.LaunchProfile) -> None:
        self.profile = profile
        self.browser: FakeBrowser | None = None
        self.playwright: FakeDriver | None = None
        self._config = object()
        self.closed = False
        self.init_error: Exception | None = None
        self.init_hang = False
        FakeSession.made.append(self)

    async def start(self) -> None:
        self.playwright = FakeDriver()
        if self.profile.locale == "slow":
            await asyncio.sleep(3600)
        if self.profile.locale == "delay":
            await asyncio.sleep(0.05)
        self.browser = FakeBrowser()

    def _build_context_with_proxy(self, proxy=None) -> dict:
        return {"proxy": proxy, "user_agent": "desktop", "viewport": "desktop"}

    async def _initialize_context(self, config, ctx):
        assert config is self._config
        if self.init_hang:
            await asyncio.sleep(3600)
        if self.init_error is not None:
            raise self.init_error
        return ctx

    async def close(self) -> None:
        self.closed = True
        if self.playwright is not None:
            await self.playwright.stop()
            self.playwright = None


class FakeExit(sessions.Exit):
    """A leased sticky exit that needs no proxy provider."""

    def proxy_url(self) -> str:
        return f"http://{self.sticky}"


@pytest.fixture
def released(monkeypatch):
    calls: list[tuple[str, bool]] = []

    def release_exit(exit, *, burned=False):
        calls.append((exit.sticky, burned))

    monkeypatch.setattr(sessions, "release_exit", release_exit)
    return calls


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def fake_pool(monkeypatch):
    asyncio.run(bp.close_all())
    FakeSession.made = []
    clock = Clock()
    monkeypatch.setattr(bp, "_new_session", FakeSession)
    monkeypatch.setattr(bp, "_clock", clock)
    monkeypatch.setattr(bp, "_plugin_caps", {})
    # Keep the pool's shutdown hook out of the process-wide list other tests read.
    monkeypatch.setattr(lifecycle, "_closers", [])
    yield clock
    asyncio.run(bp.close_all())


async def on_loop(fn):
    return await bp.run(fn)


async def settle_tasks() -> None:
    """Let the pool's spawned closes run (they are tasks on the browser loop)."""

    async def body():
        for _ in range(5):
            await asyncio.sleep(0)

    await bp.run(body)


# -- browsers --------------------------------------------------------------


@pytest.mark.asyncio
async def test_sequential_pages_share_one_browser_with_fresh_contexts():
    async def body():
        async with bp.page("p", proxy="http://exit-1") as first:
            assert not first.warm_browser and first.launch_ms >= 0
            assert first.context.options["proxy"] == "http://exit-1"
            assert first.page.timeouts == [15000, 15000]
        async with bp.page("p", proxy="http://exit-2") as second:
            assert second.warm_browser and second.launch_ms == 0
            assert second.context is not first.context
        return first, second

    first, second = await on_loop(body)
    assert len(FakeSession.made) == 1
    assert first.context.closed and second.context.closed
    assert not FakeSession.made[0].closed
    assert await bp.stats() == {"browsers": 1, "draining": 0, "pages": 0, "kept": 0}


@pytest.mark.asyncio
async def test_warm_launches_once_and_the_first_page_skips_the_launch():
    await bp.warm()
    await bp.warm()

    async def body():
        async with bp.page("google-search") as pooled:
            return pooled.warm_browser

    assert await on_loop(body) is True
    assert len(FakeSession.made) == 1
    assert (await bp.stats())["pages"] == 0


@pytest.mark.asyncio
async def test_page_runs_only_on_the_browser_loop():
    with pytest.raises(RuntimeError, match="browser loop"):
        async with bp.page("p"):
            pass

    async def where():
        return asyncio.get_running_loop()

    assert await bp.run(where) is get_browser_loop()


@pytest.mark.asyncio
async def test_mobile_shares_the_desktop_browser_and_sets_ua_and_viewport():
    async def body():
        async with bp.page("g", bp.LaunchProfile(mobile=True)) as mobile:
            assert mobile.context.options["user_agent"].startswith(
                "Mozilla/5.0 (Android"
            )
            assert mobile.context.options["viewport"] == {"width": 412, "height": 915}
        async with bp.page("g") as desktop:
            assert desktop.warm_browser
            assert desktop.context.options["user_agent"] == "desktop"

    await on_loop(body)
    assert len(FakeSession.made) == 1


@pytest.mark.asyncio
async def test_context_options_override_and_proxy_callable_is_called_per_context():
    calls = []

    def lease():
        calls.append(1)
        return f"http://exit-{len(calls)}"

    async def body():
        async with bp.page(
            "p", proxy=lease, context_options={"timezone_id": "UTC"}
        ) as a:
            assert a.context.options["proxy"] == "http://exit-1"
            assert a.context.options["timezone_id"] == "UTC"
            assert a.proxy == "http://exit-1"

    await on_loop(body)
    assert calls == [1]


@pytest.mark.asyncio
async def test_browser_cap_closes_the_least_recently_used_idle_browser(
    monkeypatch, fake_pool
):
    monkeypatch.setattr(bp, "_MAX_BROWSERS", 2)
    profiles = [
        bp.LaunchProfile(),
        bp.LaunchProfile(block_webrtc=True),
        bp.LaunchProfile(headless=False),
    ]

    async def body():
        for profile in profiles:
            async with bp.page("p", profile):
                pass
            fake_pool.now += 1

    await on_loop(body)
    await settle_tasks()
    first, second, third = FakeSession.made
    assert first.closed and not second.closed and not third.closed
    assert (await bp.stats())["browsers"] == 2


@pytest.mark.asyncio
async def test_a_busy_browser_is_closed_only_after_its_last_page(monkeypatch):
    monkeypatch.setattr(bp, "_MAX_BROWSERS", 1)
    holding = asyncio.Event()
    release = asyncio.Event()

    async def hold():
        async with bp.page("a", bp.LaunchProfile()) as pooled:
            holding.set()
            await release.wait()
            return pooled

    async def body():
        task = asyncio.create_task(hold())
        await holding.wait()
        async with bp.page("b", bp.LaunchProfile(block_webrtc=True)):
            # The cap dropped the busy browser but must not close it under "a".
            assert not FakeSession.made[0].closed
        release.set()
        pooled = await task
        for _ in range(5):
            await asyncio.sleep(0)
        return pooled

    pooled = await on_loop(body)
    assert pooled.context.closed
    assert FakeSession.made[0].closed and FakeSession.made[0].playwright is None
    assert not FakeSession.made[1].closed


@pytest.mark.asyncio
async def test_disconnect_relaunches_and_defers_the_close_of_the_dead_browser():
    async def body():
        async with bp.page("p") as inflight:
            inflight.context.browser.disconnect()
            assert not FakeSession.made[0].closed  # its page is still open
            async with bp.page("p") as after:
                assert not after.warm_browser  # a new browser was launched
        for _ in range(5):
            await asyncio.sleep(0)

    await on_loop(body)
    assert len(FakeSession.made) == 2
    assert FakeSession.made[0].closed
    assert not FakeSession.made[1].closed


@pytest.mark.asyncio
async def test_a_wedged_new_context_drops_the_browser(monkeypatch):
    monkeypatch.setattr(bp, "_CONTEXT_TIMEOUT_S", 0.05)

    async def body():
        async with bp.page("p"):
            pass
        FakeSession.made[0].browser.hang = True
        with pytest.raises(TimeoutError):
            async with bp.page("p"):
                pass
        for _ in range(5):
            await asyncio.sleep(0)
        async with bp.page("p") as fresh:
            assert not fresh.warm_browser

    await on_loop(body)
    assert FakeSession.made[0].closed and len(FakeSession.made) == 2


@pytest.mark.asyncio
async def test_idle_browsers_are_reaped_default_profile_lasts_longer(fake_pool):
    async def body():
        async with bp.page("p"):
            pass
        async with bp.page("p", bp.LaunchProfile(block_webrtc=True)):
            pass

    await on_loop(body)
    fake_pool.now += bp._BROWSER_IDLE_S + 1
    await on_loop(_reap)
    await settle_tasks()
    default, other = FakeSession.made
    assert other.closed and not default.closed
    fake_pool.now += bp._DEFAULT_BROWSER_IDLE_S
    await on_loop(_reap)
    await settle_tasks()
    assert default.closed


async def _reap():
    bp._get_pool().reap()


@pytest.mark.asyncio
async def test_idle_zero_closes_the_browser_once_its_pages_end(monkeypatch):
    monkeypatch.setattr(bp, "_BROWSER_IDLE_S", 0)
    monkeypatch.setattr(bp, "_DEFAULT_BROWSER_IDLE_S", 0)

    async def body():
        async with bp.page("p"):
            pass
        for _ in range(5):
            await asyncio.sleep(0)

    await on_loop(body)
    assert FakeSession.made[0].closed


@pytest.mark.asyncio
async def test_idle_zero_keeps_a_browser_that_holds_a_live_kept_context(
    monkeypatch, fake_pool
):
    monkeypatch.setattr(bp, "_BROWSER_IDLE_S", 0)
    monkeypatch.setattr(bp, "_DEFAULT_BROWSER_IDLE_S", 0)

    async def body():
        async with bp.page("indeed", kept="indeed:us"):
            pass
        bp._get_pool().reap()
        for _ in range(5):
            await asyncio.sleep(0)

    await on_loop(body)
    assert not FakeSession.made[0].closed
    fake_pool.now += bp._KEPT_IDLE_S + 1  # the kept context idles out, then the browser
    await on_loop(_reap)
    await on_loop(_reap)
    await settle_tasks()
    assert FakeSession.made[0].closed


@pytest.mark.asyncio
async def test_a_cancelled_launch_stops_its_driver():
    async def launch():
        async with bp.page("p", bp.LaunchProfile(locale="slow")):
            pass

    task = asyncio.create_task(bp.run(launch))
    await asyncio.wait_for(asyncio.to_thread(_wait_until, lambda: FakeSession.made), 5)
    driver = FakeSession.made[0].playwright
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.05)
    assert driver.stopped and FakeSession.made[0].playwright is None
    assert await bp.stats() == {"browsers": 0, "draining": 0, "pages": 0, "kept": 0}


@pytest.mark.asyncio
async def test_a_failed_browser_close_still_stops_the_driver():
    session = FakeSession(bp.DEFAULT_PROFILE)
    await session.start()
    driver = session.playwright

    async def broken_close():
        raise RuntimeError("browser already gone")

    session.close = broken_close
    await bp._close_session(session)
    assert driver.stopped and session.playwright is None


def test_a_browser_close_and_its_driver_stop_fit_the_shutdown_cap():
    # lifecycle cancels a pool's close at CLOSE_SECONDS; the driver stop comes last.
    assert 2 * bp._CLOSE_TIMEOUT_S < lifecycle.CLOSE_SECONDS


@pytest.mark.asyncio
async def test_a_wedged_new_page_drops_the_browser(monkeypatch):
    monkeypatch.setattr(bp, "_CONTEXT_TIMEOUT_S", 0.05)

    async def body():
        async with bp.page("p"):
            pass
        FakeSession.made[0].browser.page_hang = True
        with pytest.raises(TimeoutError):
            async with bp.page("p"):
                pass
        for _ in range(5):
            await asyncio.sleep(0)
        async with bp.page("p") as fresh:
            assert not fresh.warm_browser

    await on_loop(body)
    assert FakeSession.made[0].closed and len(FakeSession.made) == 2
    assert FakeSession.made[0].browser.contexts[1].closed  # the hung page's context


@pytest.mark.asyncio
async def test_a_context_whose_init_fails_or_is_cancelled_is_closed():
    async def use():
        async with bp.page("p"):
            pass

    async def body():
        await use()
        session = FakeSession.made[0]
        session.init_error = RuntimeError("add_init_script failed")
        with pytest.raises(RuntimeError):
            await use()
        session.init_error = None
        session.init_hang = True
        task = asyncio.create_task(use())
        for _ in range(10):
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        for _ in range(5):
            await asyncio.sleep(0)
        return session.browser.contexts

    contexts = await on_loop(body)
    assert len(contexts) == 3 and all(c.closed for c in contexts)
    assert not FakeSession.made[0].closed  # a failed init is not a dead browser


@pytest.mark.asyncio
async def test_browser_cap_spares_the_browser_holding_a_kept_context(
    monkeypatch, fake_pool
):
    monkeypatch.setattr(bp, "_MAX_BROWSERS", 2)

    async def body():
        async with bp.page("indeed", bp.LaunchProfile(block_webrtc=True), kept="k"):
            pass
        fake_pool.now += 1
        async with bp.page("p"):  # used more recently than the kept one
            pass
        fake_pool.now += 1
        async with bp.page("p", bp.LaunchProfile(headless=False)):
            pass
        for _ in range(5):
            await asyncio.sleep(0)

    await on_loop(body)
    kept_browser, default, headful = FakeSession.made
    assert default.closed and not kept_browser.closed and not headful.closed
    assert (await bp.stats())["kept"] == 1


@pytest.mark.asyncio
async def test_a_caller_waiting_on_another_launch_reports_the_wait():
    profile = bp.LaunchProfile(locale="delay")  # the fake launch takes 50 ms

    async def use():
        async with bp.page("p", profile) as pooled:
            return pooled

    async def body():
        return await asyncio.gather(use(), use())

    first, second = await on_loop(body)
    assert len(FakeSession.made) == 1
    assert first.launch_ms >= 40 and second.launch_ms >= 40
    assert not first.warm_browser and not second.warm_browser


# -- caps --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_global_page_cap_queues_in_order(monkeypatch):
    monkeypatch.setattr(bp, "_MAX_PAGES", 2)
    order: list[str] = []
    release = asyncio.Event()

    async def hold(name: str, plugin: str):
        async with bp.page(plugin) as pooled:
            order.append(name)
            await release.wait()
            return pooled

    async def body():
        tasks = [asyncio.create_task(hold(name, f"plugin-{name}")) for name in "abc"]
        for _ in range(10):
            await asyncio.sleep(0)
        assert order == ["a", "b"]  # c waits for a slot
        assert bp._get_pool().stats()["pages"] == 2
        await asyncio.sleep(0.05)
        release.set()
        return await asyncio.gather(*tasks)

    pages = await on_loop(body)
    assert order == ["a", "b", "c"]
    assert pages[2].queue_ms >= 40 and pages[0].queue_ms < 40  # c's wait, not a's


@pytest.mark.asyncio
async def test_plugin_cap_holds_one_plugin_without_blocking_others():
    bp.set_plugin_cap("slow", 1)
    entered: list[str] = []
    release = asyncio.Event()

    async def hold(plugin: str):
        async with bp.page(plugin):
            entered.append(plugin)
            await release.wait()

    async def body():
        tasks = [
            asyncio.create_task(hold(plugin)) for plugin in ("slow", "slow", "fast")
        ]
        for _ in range(10):
            await asyncio.sleep(0)
        assert sorted(entered) == ["fast", "slow"]
        release.set()
        await asyncio.gather(*tasks)

    await on_loop(body)
    assert entered.count("slow") == 2


# -- cancellation --------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelling_the_caller_closes_only_its_own_context():
    holding = asyncio.Event()
    pages: dict[str, bp.PooledPage] = {}

    async def hold(name: str):
        async with bp.page("p") as pooled:
            pages[name] = pooled
            if len(pages) == 2:
                holding.set()
            await asyncio.sleep(3600)

    async def sibling():
        async with bp.page("q") as pooled:
            pages["sibling"] = pooled
            await asyncio.sleep(0.2)
            return pooled.context.closed

    async def start():
        return asyncio.create_task(sibling())

    sibling_task = await bp.run(start)
    victim = asyncio.create_task(bp.run(lambda: hold("victim")))
    other = asyncio.create_task(bp.run(lambda: hold("other")))
    await asyncio.wait_for(asyncio.to_thread(_wait_until, holding.is_set), 5)
    victim.cancel()
    with pytest.raises(asyncio.CancelledError):
        await victim
    await asyncio.sleep(0.05)
    assert pages["victim"].context.closed
    assert not pages["other"].context.closed
    assert not FakeSession.made[0].closed

    async def sibling_result():
        return await sibling_task

    assert await bp.run(sibling_result) is False  # still open while it worked
    other.cancel()
    with pytest.raises(asyncio.CancelledError):
        await other
    await asyncio.sleep(0.05)
    assert (await bp.stats())["pages"] == 0
    assert len(FakeSession.made) == 1 and not FakeSession.made[0].closed


def _wait_until(predicate) -> None:
    # The state lives on the browser loop; poll it from a worker thread.
    while not predicate():
        time.sleep(0.01)


@pytest.mark.asyncio
async def test_an_error_in_the_body_still_closes_the_context():
    async def body():
        with pytest.raises(ValueError):
            async with bp.page("p") as pooled:
                raise ValueError("parse failed")
        return pooled

    pooled = await on_loop(body)
    assert pooled.context.closed
    assert (await bp.stats())["pages"] == 0


# -- kept contexts ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_kept_context_is_reused_and_only_its_page_closes():
    leases = []

    def lease():
        leases.append(1)
        return "http://sticky-us"

    async def body():
        async with bp.page("indeed", kept="indeed:us", proxy=lease) as first:
            assert first.kept == "indeed:us" and not first.warm_context
        async with bp.page("indeed", kept="indeed:us", proxy=lease) as second:
            assert second.warm_context and second.warm_browser
            assert second.proxy == "http://sticky-us"
        return first, second

    first, second = await on_loop(body)
    assert first.context is second.context
    assert first.page.closed and second.page.closed
    assert not first.context.closed
    assert leases == [1]  # the lease is taken only when the context is built
    assert (await bp.stats())["kept"] == 1


@pytest.mark.asyncio
async def test_kept_context_expires_when_idle_or_old(fake_pool):
    async def use():
        async with bp.page("indeed", kept="indeed:us") as pooled:
            return pooled

    first = await on_loop(use)
    fake_pool.now += bp._KEPT_IDLE_S + 1
    second = await on_loop(use)
    await settle_tasks()
    assert second.context is not first.context and first.context.closed

    # Used often enough never to idle out, but replaced once it is too old.
    step = bp._KEPT_IDLE_S - 100
    seen = []
    while (len(seen) + 1) * step < bp._KEPT_MAX_AGE_S:
        fake_pool.now += step
        seen.append(1)
        assert (await on_loop(use)).context is second.context
    fake_pool.now += step
    third = await on_loop(use)
    await settle_tasks()
    assert third.context is not second.context and second.context.closed


@pytest.mark.asyncio
async def test_reaper_closes_idle_kept_contexts(fake_pool):
    async def use():
        async with bp.page("indeed", kept="indeed:us") as pooled:
            return pooled

    pooled = await on_loop(use)
    fake_pool.now += bp._KEPT_IDLE_S + 1
    await on_loop(_reap)
    await settle_tasks()
    assert pooled.context.closed and (await bp.stats())["kept"] == 0


@pytest.mark.asyncio
async def test_burn_retires_the_kept_context_after_its_pages_end():
    release = asyncio.Event()
    holding = asyncio.Event()

    async def sibling():
        async with bp.page("indeed", kept="indeed:us") as pooled:
            holding.set()
            await release.wait()
            return pooled

    async def body():
        task = asyncio.create_task(sibling())
        await holding.wait()
        async with bp.page("indeed", kept="indeed:us") as burned:
            burned.burn("cloudflare block")
        assert not burned.context.closed  # the sibling still uses it
        release.set()
        await task
        for _ in range(5):
            await asyncio.sleep(0)
        assert burned.context.closed
        async with bp.page("indeed", kept="indeed:us") as fresh:
            assert fresh.context is not burned.context

    await on_loop(body)


@pytest.mark.asyncio
async def test_kept_context_retires_after_max_navigations(monkeypatch):
    monkeypatch.setattr(bp, "_KEPT_MAX_NAVIGATIONS", 2)

    async def body():
        async with bp.page("indeed", kept="k") as first:
            first.page.navigate()
            first.page.navigate()
        for _ in range(5):
            await asyncio.sleep(0)
        async with bp.page("indeed", kept="k") as second:
            assert second.context is not first.context
        return first

    first = await on_loop(body)
    assert first.context.closed


@pytest.mark.asyncio
async def test_kept_cap_evicts_the_least_recently_used(monkeypatch):
    monkeypatch.setattr(bp, "_MAX_KEPT", 2)

    async def use(key: str):
        async with bp.page("indeed", kept=key) as pooled:
            return pooled

    async def body():
        a = await use("a")
        await use("b")
        await use("a")  # a is now the most recent
        await use("c")  # so b goes
        for _ in range(5):
            await asyncio.sleep(0)
        return a

    a = await on_loop(body)
    pool_keys = await bp.run(_kept_keys)
    assert pool_keys == ["a", "c"]
    assert not a.context.closed


async def _kept_keys():
    return list(bp._get_pool().kept)


@pytest.mark.asyncio
async def test_kept_cap_zero_turns_kept_contexts_off(monkeypatch):
    monkeypatch.setattr(bp, "_MAX_KEPT", 0)

    async def body():
        async with bp.page("indeed", kept="indeed:us") as pooled:
            assert pooled.kept is None
        return pooled

    pooled = await on_loop(body)
    assert pooled.context.closed


@pytest.mark.asyncio
async def test_pages_per_kept_context_are_capped(monkeypatch):
    monkeypatch.setattr(bp, "_KEPT_PAGES", 1)
    entered = []
    release = asyncio.Event()

    async def hold():
        async with bp.page("indeed", kept="indeed:us"):
            entered.append(1)
            await release.wait()

    async def body():
        tasks = [asyncio.create_task(hold()) for _ in range(2)]
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(entered) == 1
        release.set()
        await asyncio.gather(*tasks)

    await on_loop(body)
    assert len(entered) == 2


@pytest.mark.asyncio
async def test_two_siblings_that_both_burn_close_the_kept_context_once():
    holding: list[bp.PooledPage] = []
    release = asyncio.Event()

    async def burner():
        async with bp.page("indeed", kept="indeed:us") as pooled:
            holding.append(pooled)
            await release.wait()
            pooled.burn("cloudflare block")

    async def body():
        tasks = [asyncio.create_task(burner()) for _ in range(2)]
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(holding) == 2 and holding[0].context is holding[1].context
        release.set()
        await asyncio.gather(*tasks)
        for _ in range(5):
            await asyncio.sleep(0)

    await on_loop(body)
    context = holding[0].context
    assert context.closed and context.closes == 1
    assert (await bp.stats())["kept"] == 0


@pytest.mark.asyncio
async def test_a_sibling_leaving_after_the_navigation_cap_closes_the_context(
    monkeypatch,
):
    monkeypatch.setattr(bp, "_KEPT_MAX_NAVIGATIONS", 2)
    holding = asyncio.Event()
    release = asyncio.Event()

    async def sibling():
        async with bp.page("indeed", kept="k"):
            holding.set()
            await release.wait()

    async def body():
        task = asyncio.create_task(sibling())
        await holding.wait()
        async with bp.page("indeed", kept="k") as first:
            first.page.navigate()
            first.page.navigate()
        assert not first.context.closed  # the sibling still uses it
        release.set()
        await task
        for _ in range(5):
            await asyncio.sleep(0)
        assert first.context.closed and first.context.closes == 1
        async with bp.page("indeed", kept="k") as fresh:
            assert fresh.context is not first.context

    await on_loop(body)


@pytest.mark.asyncio
async def test_a_kept_context_whose_new_page_fails_is_replaced():
    async def use():
        async with bp.page("indeed", kept="k") as pooled:
            return pooled

    async def body():
        first = await use()
        first.context.broken = True  # the context crashed; the browser is fine
        with pytest.raises(RuntimeError):
            await use()
        for _ in range(5):
            await asyncio.sleep(0)
        second = await use()
        return first, second

    first, second = await on_loop(body)
    assert second.context is not first.context and first.context.closed
    assert not FakeSession.made[0].closed and len(FakeSession.made) == 1


@pytest.mark.asyncio
async def test_an_error_leaving_a_kept_page_burns_it_but_a_cancel_does_not():
    holder: dict[str, bp.PooledPage] = {}

    async def hang():
        async with bp.page("indeed", kept="k") as pooled:
            holder["first"] = pooled
            await asyncio.sleep(3600)

    async def body():
        task = asyncio.create_task(hang())
        for _ in range(10):
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        context = holder["first"].context
        async with bp.page("indeed", kept="k") as after_cancel:
            assert after_cancel.context is context  # a Stop keeps the clearance
        with pytest.raises(TimeoutError):
            async with bp.page("indeed", kept="k"):
                raise TimeoutError("no commit: dead sticky exit")
        for _ in range(5):
            await asyncio.sleep(0)
        assert context.closed
        async with bp.page("indeed", kept="k") as after_error:
            assert after_error.context is not context

    await on_loop(body)


# -- leased exits ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_fresh_contexts_leased_exit_is_given_back_on_exit(released):
    async def body():
        async with bp.page("p", proxy=lambda: FakeExit("us", "a1")) as clean:
            assert clean.proxy == "http://a1"
            assert clean.context.options["proxy"] == "http://a1"
            assert released == []  # held while the context lives
        async with bp.page("p", proxy=lambda: FakeExit("us", "a2")) as blocked:
            blocked.burn("captcha wall")

    await on_loop(body)
    assert released == [("a1", False), ("a2", True)]


@pytest.mark.asyncio
async def test_a_failed_context_gives_its_lease_back(monkeypatch, released):
    monkeypatch.setattr(bp, "_CONTEXT_TIMEOUT_S", 0.05)

    async def body():
        for kept, sticky in ((None, "f1"), ("k", "f2")):
            async with bp.page("p"):  # (re)launch a browser, then wedge it
                pass
            FakeSession.made[-1].browser.hang = True
            with pytest.raises(TimeoutError):
                async with bp.page(
                    "q", kept=kept, proxy=lambda s=sticky: FakeExit("us", s)
                ):
                    pass
            for _ in range(5):
                await asyncio.sleep(0)

    await on_loop(body)
    assert released == [("f1", False), ("f2", False)]


@pytest.mark.asyncio
async def test_a_kept_lease_is_given_back_once_when_the_context_closes(released):
    stickies = iter(["k1", "k2"])

    def lease():
        return FakeExit("us", next(stickies))

    async def body():
        async with bp.page("indeed", kept="k", proxy=lease) as first:
            pass
        async with bp.page("indeed", kept="k", proxy=lease) as second:
            assert second.proxy == "http://k1" and released == []
            second.burn("security wall")
        for _ in range(5):
            await asyncio.sleep(0)
        assert released == [("k1", True)]  # quarantined: it was burned
        async with bp.page("indeed", kept="k", proxy=lease) as third:
            assert third.proxy == "http://k2"
        return first

    first = await on_loop(body)
    assert first.context.closes == 1
    assert released == [("k1", True)]


# -- page set-up -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resource_and_url_blocking():
    async def body():
        async with bp.page(
            "tiktok",
            disable_resources={"image", "media", "font"},
            block_url_patterns=("mime_type=video", ".mp4"),
            extra_headers={"Accept-Language": "en-US"},
            timeout_ms=5000,
        ) as pooled:
            return pooled.page

    page = await on_loop(body)
    assert page.headers == {"Accept-Language": "en-US"}
    assert page.timeouts == [5000, 5000]
    ((pattern, handler),) = page.routes
    assert pattern == "**/*"
    cases = {
        ("https://t.com/a.png", "image"): "abort",
        ("https://t.com/s.css", "stylesheet"): "continue",
        ("https://t.com/api?mime_type=video_mp4", "fetch"): "abort",
        ("https://t.com/v/1.mp4", "xhr"): "abort",
        ("https://t.com/api/item_list", "xhr"): "continue",
    }
    for (url, kind), expected in cases.items():
        route = FakeRoute(url, kind)
        await handler(route)
        assert route.outcome == expected, url


@pytest.mark.asyncio
async def test_default_drops_scrapling_resources_and_false_routes_nothing():
    async def body():
        async with bp.page("p") as dropping:
            pass
        async with bp.page("p", disable_resources=False) as plain:
            pass
        return dropping.page, plain.page

    dropping, plain = await on_loop(body)
    assert plain.routes == []  # no route keeps Chromium's HTTP cache on
    handler = dropping.routes[0][1]
    route = FakeRoute("https://x.com/s.css", "stylesheet")
    await handler(route)
    assert route.outcome == "abort"


@pytest.mark.asyncio
async def test_the_pool_closes_at_host_shutdown():
    async def body():
        async with bp.page("p"):
            pass

    await on_loop(body)
    assert lifecycle._closers == [bp.close_all]
    await lifecycle.close_all()
    assert FakeSession.made[0].closed
    assert await bp.stats() == {"browsers": 0, "draining": 0, "pages": 0, "kept": 0}


@pytest.mark.asyncio
async def test_close_all_closes_everything_and_starts_afresh():
    async def body():
        async with bp.page("indeed", kept="k"):
            pass
        async with bp.page("p", bp.LaunchProfile(block_webrtc=True)):
            pass

    await on_loop(body)
    await bp.close_all()
    assert all(s.closed and s.playwright is None for s in FakeSession.made)
    assert await bp.stats() == {"browsers": 0, "draining": 0, "pages": 0, "kept": 0}

    async def again():
        async with bp.page("p") as pooled:
            return pooled.warm_browser

    assert await on_loop(again) is False


# -- scrapling contract -----------------------------------------------------------


def test_scrapling_is_the_pinned_version():
    # browser_pool and settle call scrapling internals; re-check them on upgrade.
    assert version("scrapling") == "0.4.15"


def test_scrapling_private_api_still_has_the_shape_the_pool_uses():
    from scrapling.engines._browsers._base import StealthySessionMixin
    from scrapling.engines.constants import EXTRA_RESOURCES
    from scrapling.fetchers import AsyncStealthySession, ProxyRotator

    session = AsyncStealthySession(
        headless=True,
        block_webrtc=True,
        hide_canvas=True,
        locale="en-US",
        proxy_rotator=ProxyRotator([bp._UNUSED_ROTATOR_PROXY]),
    )
    options = session._build_context_with_proxy("http://user:pw@proxy.test:8080")
    assert options["proxy"] == {
        "server": "http://proxy.test:8080",
        "username": "user",
        "password": "pw",
    }
    assert {"user_agent", "viewport", "screen"} <= set(options)
    assert session._build_context_with_proxy(None)["proxy"] is None
    assert list(inspect.signature(session._initialize_context).parameters) == [
        "config",
        "ctx",
    ]
    assert inspect.iscoroutinefunction(session._initialize_context)
    assert inspect.iscoroutinefunction(session._cloudflare_solver)
    assert (
        next(iter(inspect.signature(session._cloudflare_solver).parameters)) == "page"
    )
    assert session._config is not None and session.browser is None
    assert session.playwright is None
    # Rotator mode must launch a plain browser (not a persistent context).
    start = inspect.getsource(AsyncStealthySession.start)
    assert "elif self._config.proxy_rotator:" in start
    assert "self.browser = await self.playwright.chromium.launch(" in start
    assert {"image", "font", "media", "stylesheet"} <= set(EXTRA_RESOURCES)
    detect = StealthySessionMixin._detect_cloudflare
    assert detect("<script>cType: 'managed'</script>") == "managed"
    assert detect("<html><body>hi</body></html>") is None
    assert StealthySessionMixin._challenge_cleared("<p>ok</p>", "managed")
