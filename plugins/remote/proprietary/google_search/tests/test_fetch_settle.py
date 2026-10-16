"""How a render settles before its HTML is taken, checked on fake pages.

Network idle cost 5.1-5.8 s on every render (Google's telemetry never lets the
network go quiet), and the expansion clicked the PAA pair div with
actionability waits and then slept a fixed 1.5 s. The settle now keys off the
page's load event, the organic results and the answers themselves; the old
path stays behind ``GOOGLE_SEARCH_FAST_SETTLE=0``.
"""

import asyncio
from typing import ClassVar

import pytest

from proprietary.google_search import fetch

SERP = "https://www.google.com/search?q=pie&gl=us&hl=en"


class _Toggle:
    """A PAA question toggle; ``sticks=False`` ignores its first click, as one
    fired before the page's JS bound its handler does."""

    def __init__(self, sticks: bool = True) -> None:
        self.expanded = "false"
        self.sticks = sticks
        self.clicks: list[dict] = []

    async def click(self, **kwargs) -> None:
        self.clicks.append(kwargs)
        if self.sticks or len(self.clicks) > 1:
            self.expanded = "true"

    async def get_attribute(self, name: str) -> str:
        assert name == "aria-expanded"
        return self.expanded


class _Page:
    """A Playwright page that records its waits; ``answers=False`` makes the
    PAA answer wait run out, ``desktop=False`` serves the mobile layout."""

    def __init__(
        self,
        url: str = SERP,
        toggles: list[_Toggle] | None = None,
        answers: bool = True,
        desktop: bool = True,
    ) -> None:
        self.url = url
        self.desktop = desktop
        self.aio: _Toggle | None = None  # the AI Overview's "Show more"
        self.toggles = toggles if toggles is not None else [_Toggle(), _Toggle()]
        self.answers = answers
        self.calls: list[tuple] = []

    async def wait_for_load_state(self, state, timeout=None):  # noqa: ASYNC109 - Playwright's signature
        self.calls.append(("load", state, timeout))

    async def wait_for_selector(self, selector, state=None, timeout=None):  # noqa: ASYNC109 - Playwright's signature
        self.calls.append(("selector", selector, state, timeout))

    async def query_selector(self, selector):
        self.calls.append(("query", selector))
        if selector == fetch._AIO_SHOW_MORE_SEL:
            return self.aio
        return object() if selector == "div.tF2Cxc" and self.desktop else None

    async def query_selector_all(self, selector):
        self.calls.append(("query_all", selector))
        return self.toggles

    async def wait_for_function(self, js, arg=None, timeout=None, polling=None):  # noqa: ASYNC109 - Playwright's signature
        self.calls.append(("function", arg, timeout))
        if js == fetch._PAA_ANSWERED_JS and not self.answers:
            raise TimeoutError("answers never came")

    async def wait_for_timeout(self, ms):
        self.calls.append(("sleep", ms))

    async def evaluate(self, js, *args):
        self.calls.append(("evaluate", js))

    def kinds(self) -> list[str]:
        return [call[0] for call in self.calls]


def test_settles_on_load_then_organic_results_never_on_rso():
    page = _Page()
    asyncio.run(fetch._expand_blocks(page))

    load, ready = page.calls[0], page.calls[1]
    assert load[:2] == ("load", "load")
    assert ready[0] == "selector" and ready[2] == "attached"
    assert "div.tF2Cxc" in ready[1] and "#rso" not in ready[1]


def test_questions_open_bottom_first_and_the_overview_after_them():
    """A forced click aims where its target is at that instant, and every
    expansion pushes what is below it down, so nothing above a target may
    still be opening when it is clicked."""
    order: list[str] = []

    class _Named(_Toggle):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

        async def click(self, **kwargs) -> None:
            order.append(self.name)
            await super().click(**kwargs)

    page = _Page(toggles=[_Named("q1"), _Named("q2"), _Named("q3")])
    page.aio = _Named("aio")
    asyncio.run(fetch._expand_blocks(page))

    assert order == ["q3", "q2", "q1", "aio"]


def test_paa_opens_its_real_toggle_with_forced_clicks():
    page = _Page()
    asyncio.run(fetch._expand_blocks(page))

    [selector] = [call[1] for call in page.calls if call[0] == "query_all"]
    assert "[role=button][aria-expanded='false']" in selector
    for toggle in page.toggles:
        assert toggle.clicks == [{"force": True, "no_wait_after": True, "timeout": 500}]


def test_a_toggle_clicked_too_early_is_clicked_once_more():
    early, ready = _Toggle(sticks=False), _Toggle()
    page = _Page(toggles=[early, ready], answers=False)
    asyncio.run(fetch._expand_blocks(page))

    # Only the still-collapsed one: a second click would close an open one.
    assert (len(early.clicks), len(ready.clicks)) == (2, 1)
    assert early.expanded == "true"
    answer_waits = [c for c in page.calls if c[0] == "function" and c[1] == 2]
    assert [c[2] for c in answer_waits] == [
        fetch._PAA_ANSWER_CAP_MS,
        fetch._PAA_RETRY_CAP_MS,
    ]


def test_answered_toggles_are_never_clicked_twice():
    early = _Toggle(sticks=False)
    page = _Page(toggles=[early])
    asyncio.run(fetch._expand_blocks(page))

    # The answers came, so the toggle's state is not second-guessed.
    assert len(early.clicks) == 1


@pytest.mark.parametrize(
    ("url", "desktop", "waits"),
    [
        (SERP, True, True),
        (SERP + "&start=10", True, False),
        ("https://www.google.com/search?q=mars+rover+site%3Anasa.gov", True, False),
        (SERP, False, False),
    ],
)
def test_page_one_waits_briefly_for_a_late_paa_block(url, desktop, waits):
    page = _Page(url=url, desktop=desktop)
    asyncio.run(fetch._expand_blocks(page))

    late = ("selector", fetch._PAA_SEL, "attached", fetch._PAA_ATTACH_MS)
    assert (late in page.calls) is waits


def test_waits_for_the_answers_not_a_fixed_sleep():
    page = _Page(toggles=[_Toggle() for _ in range(6)])
    asyncio.run(fetch._expand_blocks(page))

    # Only the first four questions are opened, and the wait is on them.
    assert sum(len(t.clicks) for t in page.toggles) == 4
    answers, appended, _ = [call for call in page.calls if call[0] == "function"]
    assert answers[1:] == (4, fetch._PAA_ANSWER_CAP_MS)
    # Then the questions Google appends, until the block holds still.
    assert appended[1:] == (fetch._PAA_STABLE_MS, fetch._PAA_GRACE_CAP_MS)
    assert "sleep" not in page.kinds()


def test_no_questions_no_answer_wait():
    page = _Page(toggles=[])
    asyncio.run(fetch._expand_blocks(page))

    assert [call for call in page.calls if call[0] == "function"] == [
        ("function", [fetch._AIO_STABLE_MS, True], fetch._AIO_PROSE_CAP_MS)
    ]
    assert "sleep" not in page.kinds()


def test_an_overview_attached_after_the_clicks_is_still_opened():
    """Live, "Show more" was missing at click time on warm renders, and the
    overview read 0-680 of its ~2.5k characters; it is looked up again once
    the answers are in, then waited on until its text stops growing."""
    page = _Page()
    late = _Toggle()
    lookups = 0
    query_selector = page.query_selector

    async def attaches_late(selector):
        nonlocal lookups
        if selector == fetch._AIO_SHOW_MORE_SEL:
            lookups += 1
            page.aio = late if lookups > 1 else None
        return await query_selector(selector)

    page.query_selector = attaches_late
    assert asyncio.run(fetch._expand_blocks_fast(page)) == len(page.toggles) + 1

    assert late.clicks == [{"timeout": fetch._CLICK_TIMEOUT_MS}]
    waits = [call for call in page.calls if call[0] == "function"]
    settled = ("function", [fetch._AIO_STABLE_MS, True], fetch._AIO_PROSE_CAP_MS)
    assert waits[-2:] == [settled, settled]  # before and after the late click


def test_later_pages_do_not_wait_for_an_overview_that_never_comes():
    page = _Page(url=SERP + "&start=10", toggles=[])
    asyncio.run(fetch._expand_blocks(page))

    assert [call for call in page.calls if call[0] == "function"] == [
        ("function", [fetch._AIO_STABLE_MS, False], fetch._AIO_PROSE_CAP_MS)
    ]


def test_the_dom_is_shrunk_last():
    page = _Page()
    asyncio.run(fetch._expand_blocks(page))

    assert page.calls[-1] == ("evaluate", fetch._SHRINK_JS)
    # Favicons keep their data URI (includeIcons), lazy images their data-src.
    assert "XNo5Ab" in fetch._SHRINK_JS
    assert "removeAttribute('src')" in fetch._SHRINK_JS


def test_shrinking_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(fetch, "_SHRINK_DOM", False)
    page = _Page()
    asyncio.run(fetch._expand_blocks(page))

    assert "evaluate" not in page.kinds()


def test_a_page_still_on_sorry_is_left_alone():
    page = _Page(url="https://www.google.com/sorry/index?continue=x")
    asyncio.run(fetch._expand_blocks(page))

    assert page.calls == []


@pytest.mark.parametrize(
    "fast",
    [
        pytest.param(False, id="kill switch"),
        pytest.param(True, id="AI Mode"),
    ],
)
def test_old_expansion_where_it_still_applies(monkeypatch, fast):
    monkeypatch.setattr(fetch, "_FAST_SETTLE", fast)
    url = SERP + "&udm=50" if fast else SERP
    page = _Page(url=url)
    asyncio.run(fetch._expand_blocks(page))

    assert ("query_all", "div.related-question-pair") in page.calls
    assert page.toggles[0].clicks == [{"timeout": 1500}]
    assert ("sleep", fetch._PAA_ANSWER_WAIT_MS) in page.calls
    assert "load" not in page.kinds()


class _Session:
    launched: ClassVar[list[dict]] = []

    def __init__(self, **kwargs) -> None:
        _Session.launched.append(kwargs)
        self.fetched: list[tuple[str, dict]] = []

    async def start(self) -> None:
        return None

    async def fetch(self, url, proxy=None, **kwargs):
        self.fetched.append((url, kwargs))
        return "page"


@pytest.fixture
def fake_browser(monkeypatch):
    _Session.launched = []
    monkeypatch.setattr(fetch, "AsyncStealthySession", _Session)
    monkeypatch.setattr(fetch, "get_proxy_url", lambda: None)
    monkeypatch.setattr(fetch, "_sessions", {})
    return _Session


@pytest.mark.parametrize(("fast", "idle"), [(True, False), (False, True)])
def test_the_browser_waits_for_network_idle_only_on_the_old_path(
    fake_browser, monkeypatch, fast, idle
):
    monkeypatch.setattr(fetch, "_FAST_SETTLE", fast)
    asyncio.run(fetch._get_session(False))

    assert fake_browser.launched[0]["network_idle"] is idle


def test_ai_mode_renders_still_wait_for_network_idle(fake_browser):
    async def main():
        await fetch._render_on_loop(SERP, None, False)
        await fetch._render_on_loop(SERP + "&udm=50", None, False)
        return fetch._sessions[False]

    session = asyncio.run(main())
    (_, serp_kwargs), (_, ai_kwargs) = session.fetched
    assert "network_idle" not in serp_kwargs
    assert ai_kwargs["network_idle"] is True
