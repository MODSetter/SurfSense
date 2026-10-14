"""Offline tests for the pooled fetch seam: navigation, challenges, walls, rotation
and the spa=1 detail path, on a fake pooled page (no browser, no network)."""

from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from proprietary.indeed import fetch
from proprietary.indeed.fetch import IndeedAccessBlockedError, IndeedSession
from proprietary.scraping import sessions

_FIXTURES = Path(__file__).parent / "fixtures"
_CHALLENGE = (
    Path(__file__).parents[2] / "scraping/tests/fixtures/cf_interstitial.html"
).read_text(encoding="utf-8")
_SPA = (_FIXTURES / "viewjob_spa.json").read_text(encoding="utf-8")
_VIEWJOB = (_FIXTURES / "viewjob_live.html").read_text(encoding="utf-8")
_OK_HTML = "<html>jobs listing</html>"
_WALL_HTML = "<html>secure.indeed.com security check</html>"
_URL = "https://www.indeed.com/jobs?q=dev"

# What the site answers a navigation with: (html, status, final url).
Answer = tuple[str, int, str]


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status
        self.headers: dict[str, str] = {}


class _Context:
    """A browser context: pages that share one share its clearance."""


class _Site:
    """Indeed as a scripted list of answers per navigation, and spa=1 by URL.

    Each page gets a new context, unless ``contexts`` lists the ones to lend
    first; ``cleared`` marks every context as already past Cloudflare.
    """

    def __init__(
        self,
        navigate: Callable[[str], Answer],
        spa: Callable[[str], tuple[int, str]] | None = None,
        *,
        contexts: list[_Context] | None = None,
        cleared: bool = False,
    ) -> None:
        self.navigate = navigate
        self.spa = spa or (lambda url: (200, _SPA))
        self.contexts = list(contexts or [])
        self.cleared = cleared
        self.navigations: list[str] = []
        self.referers: list[str | None] = []
        self.load_states: list[str] = []
        self.spa_batches: list[list[str]] = []
        self.solves = 0
        self.countries: list[str] = []
        self.pages: list[_Pooled] = []

    def opener(self, country: str):
        self.countries.append(country)

        @asynccontextmanager
        async def lend() -> AsyncIterator[_Pooled]:
            context = self.contexts.pop(0) if self.contexts else _Context()
            if self.cleared:
                fetch._cleared.add(context)
            pooled = _Pooled(self, context)
            self.pages.append(pooled)
            try:
                yield pooled
            except Exception as e:
                pooled.left_with = e
                raise

        return lend()

    def session(self) -> IndeedSession:
        async def run_here(fn):
            return await fn()

        return IndeedSession(self.opener, run_here)


class _Page:
    def __init__(self, site: _Site) -> None:
        self.site = site
        self.url = "about:blank"
        self.html = ""

    async def goto(self, url: str, **kwargs: Any) -> _Response:
        self.site.navigations.append(url)
        self.site.referers.append(kwargs.get("referer"))
        self.html, status, self.url = self.site.navigate(url)
        return _Response(status)

    async def wait_for_load_state(self, state: str, **_: Any) -> None:
        self.site.load_states.append(state)

    async def content(self) -> str:
        return self.html

    def is_closed(self) -> bool:
        return False

    async def evaluate(self, script: str, arg: list[Any]) -> list[list[Any]]:
        urls, _timeout_ms = arg
        self.site.spa_batches.append(list(urls))
        return [list(self.site.spa(u)) for u in urls]


class _Solver:
    def __init__(self, site: _Site) -> None:
        self.site = site

    async def _cloudflare_solver(self, page: _Page) -> None:
        await asyncio.sleep(0.05)  # a solve takes a while: siblings may run
        self.site.solves += 1
        page.html = _OK_HTML


class _Pooled:
    def __init__(self, site: _Site, context: _Context | None = None) -> None:
        self.context = context or _Context()
        self.page = _Page(site)
        self._session = _Solver(site)
        self.burned: str | None = None
        self.left_with: Exception | None = None

    def burn(self, reason: str) -> None:
        self.burned = self.burned or reason


def _script(*answers: Answer | str) -> Callable[[str], Answer]:
    """Answer target navigations in turn; the home page always answers clean."""
    queue = list(answers)

    def navigate(url: str) -> Answer:
        if url.endswith("indeed.com/"):
            return "<html>home</html>", 200, url
        answer = queue.pop(0)
        if answer == "OK":
            return _OK_HTML, 200, url
        if answer == "WALL":
            return _WALL_HTML, 200, "https://secure.indeed.com/auth?continue=x"
        if answer == "403":
            return "<html><body>Forbidden</body></html>", 403, url
        if answer == "CHALLENGE":
            return _CHALLENGE, 403, url
        if answer == "ERROR":
            raise RuntimeError("net::ERR_TUNNEL_CONNECTION_FAILED")
        assert isinstance(answer, tuple)
        return answer

    return navigate


@pytest.mark.asyncio
async def test_happy_path_goes_straight_to_the_page_at_domcontentloaded():
    site = _Site(_script("OK"))
    fetched = await site.session().fetch_page(_URL)
    assert fetched.html == _OK_HTML
    # No home-page warm-up, and no load or network-idle wait.
    assert site.navigations == [_URL]
    assert site.load_states == ["domcontentloaded"]
    assert site.solves == 0
    assert site.pages[0].burned is None


@pytest.mark.asyncio
async def test_a_challenge_is_solved_once_on_the_page_itself():
    site = _Site(_script("CHALLENGE"))
    fetched = await site.session().fetch_page(_URL)
    assert fetched.html == _OK_HTML
    assert site.solves == 1
    assert site.navigations == [_URL]


@pytest.mark.asyncio
async def test_a_sign_in_bounce_warms_the_home_page_once_then_retries():
    site = _Site(_script("WALL", "OK"))
    session = site.session()
    assert (await session.fetch_page(_URL)).html == _OK_HTML
    assert site.navigations == [_URL, "https://www.indeed.com/", _URL]
    assert session.rotations == 0


@pytest.mark.asyncio
async def test_a_bounce_that_survives_the_warm_up_burns_and_rotates():
    site = _Site(_script("WALL", "WALL", "OK"))
    session = site.session()
    assert (await session.fetch_page(_URL)).html == _OK_HTML
    assert session.rotations == 1
    assert site.pages[0].burned == "security wall"
    assert site.pages[1].burned is None


@pytest.mark.asyncio
async def test_rotates_past_a_403_without_wall_markers():
    # Live: an exit got 403 on /jobs with no marker in the body, and the old
    # check returned that page as jobs, so the call answered 0 items.
    site = _Site(_script("403", "OK"))
    session = site.session()
    assert (await session.fetch_page(_URL)).html == _OK_HTML
    assert session.rotations == 1
    assert site.pages[0].burned


@pytest.mark.asyncio
async def test_recovers_after_a_navigation_error_on_a_new_context():
    site = _Site(_script("ERROR", "OK"))
    session = site.session()
    assert (await session.fetch_page(_URL)).html == _OK_HTML
    assert session.rotations == 1
    # The error left the page block, which is what burns a kept context.
    assert isinstance(site.pages[0].left_with, RuntimeError)


@pytest.mark.asyncio
async def test_raises_after_exhausting_rotations():
    site = _Site(_script(*["WALL"] * 20))
    session = site.session()
    with pytest.raises(IndeedAccessBlockedError):
        await session.fetch_page(_URL)
    assert session.rotations == 3
    assert len(site.pages) == 4


@pytest.mark.asyncio
async def test_max_rotations_zero_fails_fast():
    site = _Site(_script("403", "OK"))
    session = site.session()
    with pytest.raises(IndeedAccessBlockedError):
        await session.fetch_page(_URL, max_rotations=0)
    assert session.rotations == 0


@pytest.mark.asyncio
async def test_a_stuck_page_times_out_and_rotates(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(fetch, "_PAGE_TIMEOUT_S", 0.05)
    calls = 0

    def navigate(url: str) -> Answer:
        return _OK_HTML, 200, url

    site = _Site(navigate)
    real_goto = _Page.goto

    async def goto(self: _Page, url: str, **kwargs: Any) -> _Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(5)
        return await real_goto(self, url, **kwargs)

    monkeypatch.setattr(_Page, "goto", goto)
    session = site.session()
    assert (await session.fetch_page(_URL)).html == _OK_HTML
    assert session.rotations == 1
    assert isinstance(site.pages[0].left_with, TimeoutError)


def test_the_page_timeout_is_below_the_old_75_s():
    assert fetch._PAGE_TIMEOUT_S <= 40
    assert fetch._WARM_TIMEOUT_S <= 15


@pytest.mark.asyncio
async def test_the_site_country_picks_the_context():
    site = _Site(_script("OK", "OK", "OK"))
    session = site.session()
    await session.fetch_page("https://uk.indeed.com/jobs?q=dev")
    await session.fetch_page("https://de.indeed.com/jobs?q=dev")
    await session.fetch_page(_URL)
    assert site.countries == ["gb", "de", "us"]


def test_the_pool_page_is_kept_per_country_on_a_leased_exit_in_it(
    monkeypatch: pytest.MonkeyPatch,
):
    seen: dict[str, Any] = {}

    def page(plugin: str, profile: Any, **kwargs: Any) -> str:
        seen.update(kwargs, plugin=plugin, profile=profile)
        return "page"

    monkeypatch.setattr(fetch.browser_pool, "page", page)
    assert fetch._pool_page("gb") == "page"
    assert seen["plugin"] == "indeed"
    assert seen["kept"] == "indeed:gb"
    assert seen["profile"].block_webrtc is True
    exit = seen["proxy"]()
    try:
        assert exit.country == "gb"
        assert exit.sticky and exit.sticky.startswith("in")
    finally:
        sessions.release_exit(exit)


def test_the_kept_context_has_a_kill_switch(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, Any] = {}
    monkeypatch.setattr(fetch, "_KEPT", False)
    monkeypatch.setattr(
        fetch.browser_pool, "page", lambda plugin, profile, **kw: seen.update(kw)
    )
    fetch._pool_page("us")
    assert seen["kept"] is None


def _spa_answers(statuses: dict[str, int]) -> Callable[[str], tuple[int, str]]:
    def spa(url: str) -> tuple[int, str]:
        jk = url.split("jk=")[1].split("&")[0]
        status = statuses.get(jk, 200)
        if status != 200:
            return status, ""
        answer = json.loads(_SPA)
        answer["body"]["jobKey"] = jk
        return 200, json.dumps(answer)

    return spa


def _wanted(keys: list[str]) -> Callable[[str], dict[str, str]]:
    return lambda html: {k: f"/viewjob?jk={k}&from=serp&spa=1" for k in keys}


@pytest.mark.asyncio
async def test_details_come_from_spa_in_batches_of_five_without_navigating():
    site = _Site(_script("OK"), _spa_answers({}))
    keys = [f"k{i}" for i in range(7)]
    fetched = await site.session().fetch_page(_URL, details_for=_wanted(keys))
    assert sorted(fetched.details) == sorted(keys)
    assert fetched.details["k3"]["jobKey"] == "k3"
    assert [len(batch) for batch in site.spa_batches] == [5, 2]
    assert site.navigations == [_URL]


@pytest.mark.asyncio
async def test_a_failed_spa_detail_falls_back_to_that_job_page_only():
    def navigate(url: str) -> Answer:
        return (_VIEWJOB if "/viewjob" in url else _OK_HTML), 200, url

    site = _Site(navigate, _spa_answers({"k2": 500}))
    fetched = await site.session().fetch_page(_URL, details_for=_wanted(["k1", "k2"]))
    assert sorted(fetched.details) == ["k1", "k2"]
    assert site.navigations == [_URL, "https://www.indeed.com/viewjob?jk=k2"]
    assert site.pages[0].burned is None


@pytest.mark.asyncio
async def test_two_spa_401s_retire_the_context_but_keep_the_listing():
    def navigate(url: str) -> Answer:
        if "/viewjob" in url:
            return _WALL_HTML, 200, "https://secure.indeed.com/auth"
        return _OK_HTML, 200, url

    site = _Site(navigate, _spa_answers({"k1": 401, "k2": 401}))
    session = site.session()
    keys = [f"k{i}" for i in range(1, 8)]
    fetched = await session.fetch_page(_URL, details_for=_wanted(keys))
    assert fetched.html == _OK_HTML
    assert sorted(fetched.details) == ["k3", "k4", "k5"]
    assert site.pages[0].burned == "spa 401"
    # Nothing more on the flagged exit: no second batch, no job page.
    assert [len(batch) for batch in site.spa_batches] == [5]
    assert site.navigations == [_URL]
    # Details are best-effort: the page itself is not retried.
    assert session.rotations == 0


@pytest.mark.asyncio
async def test_pages_of_one_context_keep_one_spa_batch_in_flight(monkeypatch):
    # Concurrent targets share the kept context, so its exit: 2 pages x 5 at once
    # would be 10 spa=1 requests from one IP.
    in_flight = peak = 0

    async def evaluate(self: _Page, script: str, arg: list[Any]) -> list[list[Any]]:
        nonlocal in_flight, peak
        urls, _ = arg
        in_flight += len(urls)
        peak = max(peak, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= len(urls)
        return [list(self.site.spa(u)) for u in urls]

    monkeypatch.setattr(_Page, "evaluate", evaluate)
    shared = _Context()
    site = _Site(
        _script("OK", "OK"), _spa_answers({}), contexts=[shared, shared], cleared=True
    )
    session = site.session()
    a, b = await asyncio.gather(
        session.fetch_page(_URL, details_for=_wanted([f"a{i}" for i in range(7)])),
        session.fetch_page(_URL, details_for=_wanted([f"b{i}" for i in range(7)])),
    )
    assert len(a.details) == len(b.details) == 7
    assert peak <= fetch._SPA_BATCH


@pytest.mark.asyncio
async def test_the_spa_kill_switch_loads_each_job_page(monkeypatch):
    monkeypatch.setattr(fetch, "_SPA", False)

    def navigate(url: str) -> Answer:
        return (_VIEWJOB if "/viewjob" in url else _OK_HTML), 200, url

    site = _Site(navigate)
    fetched = await site.session().fetch_page(_URL, details_for=_wanted(["k1"]))
    assert list(fetched.details) == ["k1"]
    assert site.spa_batches == []


@pytest.mark.asyncio
async def test_a_direct_job_reads_spa_from_robots_txt():
    def navigate(url: str) -> Answer:
        return "User-agent: *", 200, url

    site = _Site(navigate, _spa_answers({}), cleared=True)
    model = await site.session().fetch_job(
        "https://www.indeed.com/viewjob?jk=abc&tk=t0k", "abc"
    )
    assert model is not None and model["jobKey"] == "abc"
    assert site.navigations == ["https://www.indeed.com/robots.txt"]
    # Google never links to robots.txt: it is reached as a typed address.
    assert site.referers == [None]
    assert site.spa_batches == [["/viewjob?jk=abc&spa=1"]]


@pytest.mark.asyncio
async def test_a_direct_job_falls_back_to_its_page_when_spa_fails():
    def navigate(url: str) -> Answer:
        return (_VIEWJOB if "/viewjob" in url else "User-agent: *"), 200, url

    url = "https://www.indeed.com/viewjob?jk=17c2d37519bd8374"
    site = _Site(navigate, _spa_answers({"17c2d37519bd8374": 403}), cleared=True)
    model = await site.session().fetch_job(url, "17c2d37519bd8374")
    assert model is not None and model.get("jobInfoWrapperModel")
    assert site.navigations == ["https://www.indeed.com/robots.txt", url]


@pytest.mark.asyncio
async def test_warm_first_kill_switch_lands_on_the_home_page(monkeypatch):
    monkeypatch.setattr(fetch, "_WARM_FIRST", True)
    site = _Site(_script("OK"))
    await site.session().fetch_page(_URL)
    assert site.navigations == ["https://www.indeed.com/", _URL]


@pytest.mark.asyncio
async def test_always_solve_kill_switch_runs_the_solver_on_a_clean_page(monkeypatch):
    monkeypatch.setattr(fetch, "_ALWAYS_SOLVE", True)
    site = _Site(_script("OK"))
    assert (await site.session().fetch_page(_URL)).html == _OK_HTML
    assert site.solves == 1


def test_the_country_pin_has_a_kill_switch(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, Any] = {}
    monkeypatch.setattr(fetch, "_PIN_COUNTRY", False)
    monkeypatch.setattr(
        fetch.browser_pool, "page", lambda plugin, profile, **kw: seen.update(kw)
    )
    fetch._pool_page("gb")
    assert seen["kept"] == "indeed:gb"  # the clearance stays per Indeed country
    exit = seen["proxy"]()
    try:
        assert exit.country is None
    finally:
        sessions.release_exit(exit)


@pytest.mark.asyncio
async def test_stages_are_reported_per_attempt():
    heard: list[str] = []

    async def report(message: str) -> None:
        heard.append(message)

    token = fetch.on_stage.set(report)
    try:
        site = _Site(_script("403", "CHALLENGE"))
        await site.session().fetch_page(_URL)
    finally:
        fetch.on_stage.reset(token)
    assert heard[0] == f"fetching {_URL}"
    assert heard[1] == f"fetching {_URL} (try 2)"
    assert "solving a Cloudflare managed challenge" in heard


@pytest.mark.asyncio
async def test_a_direct_job_on_a_new_context_loads_its_page_at_once():
    # Without a clearance, spa=1 answers 403 (live c4/c6 cold): skip it.
    def navigate(url: str) -> Answer:
        return _VIEWJOB, 200, url

    url = "https://www.indeed.com/viewjob?jk=17c2d37519bd8374"
    site = _Site(navigate, _spa_answers({}))
    model = await site.session().fetch_job(url, "17c2d37519bd8374")
    assert model is not None and model.get("jobInfoWrapperModel")
    assert site.navigations == [url]
    assert site.spa_batches == []


def _challenged_until_solved(site_ref: list[_Site]) -> Callable[[str], Answer]:
    """Cloudflare challenges every navigation until a solve sets the clearance."""

    def navigate(url: str) -> Answer:
        if site_ref[0].solves == 0:
            return _CHALLENGE, 403, url
        return _OK_HTML, 200, url

    return navigate


@pytest.mark.asyncio
async def test_pages_on_a_new_context_land_one_at_a_time_so_one_solve_clears_it():
    # Live m2 cold: two targets on a new context each met a challenge and solved
    # it at once (21 and 23 s). The second now waits and lands cleared.
    shared = _Context()
    site_ref: list[_Site] = []
    site = _Site(_challenged_until_solved(site_ref), contexts=[shared, shared])
    site_ref.append(site)
    session = site.session()
    heard: list[str] = []

    async def report(message: str) -> None:
        heard.append(message)

    token = fetch.on_stage.set(report)
    try:
        a, b = await asyncio.gather(
            session.fetch_page(_URL), session.fetch_page(_URL + "&l=x")
        )
    finally:
        fetch.on_stage.reset(token)
    assert a.html == b.html == _OK_HTML
    assert site.solves == 1
    assert shared in fetch._cleared
    # The wait behind the solve is not a silent one.
    assert "waiting for the page ahead to clear Cloudflare" in heard


@pytest.mark.asyncio
async def test_a_page_waiting_behind_a_walled_one_moves_to_a_new_context():
    shared = _Context()
    answers = iter(["WALL", "WALL", "OK", "OK"])

    def navigate(url: str) -> Answer:
        if url.endswith("indeed.com/"):
            return "<html>home</html>", 200, url
        return _script(next(answers))(url)

    site = _Site(navigate, contexts=[shared, shared])
    session = site.session()
    first, second = await asyncio.gather(
        session.fetch_page(_URL),
        session.fetch_page(_URL + "&l=x"),
        return_exceptions=True,
    )
    # The first rotated after its wall; the second gave up on the walled context
    # without navigating it, and landed on a new one.
    assert {first.html, second.html} == {_OK_HTML}
    assert session.rotations == 2
    assert site.navigations.count(_URL + "&l=x") == 1


def test_browser_work_runs_on_the_browser_loop_from_a_selector_loop():
    """The Windows regression this guards: main.py runs the server on a
    SelectorEventLoop (psycopg needs it), and Selector loops cannot spawn
    subprocesses: patchright's Chromium launch died with NotImplementedError.
    The default runner hands every page to the shared, subprocess-capable
    browser loop, so a page opener that really spawns a subprocess works.
    """

    def opener(country: str):
        @asynccontextmanager
        async def lend() -> AsyncIterator[_Pooled]:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", "print('ok')", stdout=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            yield _Pooled(_Site(_script("OK")))

        return lend()

    async def main() -> None:
        session = IndeedSession(opener)
        assert (await session.fetch_page(_URL)).html == _OK_HTML

    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
