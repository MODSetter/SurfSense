"""The render's side of the /goto prefetch, the fail-fast precheck and the warm-up.

A render now hands its /goto links over as soon as the organic results attach
and again after the expansion (GS-3), the IP precheck makes one bounded
attempt on the shared transport (GS-1), and the plugin's lifespan launches the
desktop browser before the first call (GS-8). Pages, sessions and Google are
fakes; nothing leaves the machine.
"""

import asyncio
import importlib

import pytest

from proprietary.google_search import fetch, scraper
from proprietary.google_search.schemas import GoogleSearchScrapeInput
from proprietary.google_search.tests.test_fetch_settle import _Page
from proprietary.scraping import http, lifecycle

ORGANIC = ["/goto?url=a", "/goto?url=b"]
EXPANDED = [*ORGANIC, "/goto?url=paa", "/goto?url=aio"]


class _LinkPage(_Page):
    """A page whose /goto anchors are ORGANIC once settled, EXPANDED after."""

    async def evaluate(self, js, *args):
        await super().evaluate(js, *args)
        if js == fetch._LINKS_JS:
            self.calls[-1] = ("links", *args)
            return EXPANDED if args[0] else ORGANIC
        return None


class _Sink:
    def __init__(self) -> None:
        self.fed: list[list[str]] = []
        self.discarded = 0

    def feed(self, hrefs) -> None:
        self.fed.append(list(hrefs))

    def discard(self) -> None:
        self.discarded += 1


def test_the_render_feeds_organic_links_once_settled_then_the_expanded_ones():
    page = _LinkPage()
    sink = _Sink()
    asyncio.run(fetch._expand_blocks(page, sink))

    assert sink.fed == [ORGANIC, EXPANDED]
    kinds = page.kinds()
    # The organic links go out right after the settle, before any PAA click.
    first_feed = page.calls.index(("links", False))
    assert kinds[:2] == ["load", "selector"]
    assert first_feed < kinds.index("query_all")
    # The DOM is shrunk last, after the expanded links were read.
    assert page.calls[-1] == ("evaluate", fetch._SHRINK_JS)


def test_a_render_without_a_sink_reads_no_links():
    page = _LinkPage()
    asyncio.run(fetch._expand_blocks(page))

    assert "links" not in page.kinds()


def test_a_page_on_sorry_feeds_nothing():
    page = _LinkPage(url="https://www.google.com/sorry/index?continue=x")
    sink = _Sink()
    asyncio.run(fetch._expand_blocks(page, sink))

    assert sink.fed == []


class _Rendered:
    def __init__(self, good: bool) -> None:
        self.status = 200
        self.html_content = '<div class="tF2Cxc">r</div>' if good else "<p>walled</p>"


@pytest.fixture
def proxied(monkeypatch):
    """The proxied path with two fresh IPs: the first walled, the second good."""
    fetch._pool.clear()
    fetch._pool_inflight.clear()
    renders: list[tuple[str, object]] = []
    outcomes = iter([False, True])
    ips = iter(["p1", "p2"])

    async def render(url, proxy, mobile=False, sink=None):
        renders.append((proxy, sink))
        return _Rendered(next(outcomes))

    async def none(*args, **kwargs):
        return None

    async def vet(url):
        return next(ips)

    monkeypatch.setattr(fetch, "AsyncStealthySession", object)
    monkeypatch.setattr(fetch, "get_proxy_url", lambda: "http://gateway")
    monkeypatch.setattr(fetch, "_render", render)
    monkeypatch.setattr(fetch, "_vet_fresh_ip", vet)
    monkeypatch.setattr(fetch._store, "adopt", none)
    monkeypatch.setattr(fetch._store, "evict", none)
    monkeypatch.setattr(fetch._store, "publish", none)
    yield renders
    fetch._pool.clear()
    fetch._pool_inflight.clear()
    fetch._pool_pending = 0


async def test_a_walled_render_s_links_are_discarded_and_stages_reported(proxied):
    sink = _Sink()
    stages: list[str] = []

    async def hook(message: str) -> None:
        stages.append(message)

    links = fetch.link_sink.set(sink)
    hooked = fetch.stage_hook.set(hook)
    try:
        html = await fetch.fetch_serp_html("https://www.google.com/search?q=pie")
    finally:
        fetch.link_sink.reset(links)
        fetch.stage_hook.reset(hooked)

    assert html is not None and "tF2Cxc" in html
    assert [proxy for proxy, _ in proxied] == ["p1", "p2"]
    assert all(given is sink for _, given in proxied)  # handed to every render
    assert sink.discarded == 1  # the walled one only
    assert stages == [
        "vetting fresh IPs",
        "rendering on a fresh IP",
        "walled; trying another IP",
        "vetting fresh IPs",
        "rendering on a fresh IP",
    ]


def _answer(status: int, body: str) -> http.RawResponse:
    fields = {
        "status": status,
        "url": "https://www.google.com/search?q=pie",
        "headers": {},
        "cookies": {},
        "body": body.encode(),
        "history": (),
        "timings": http.Timings(True, 0, 0, 0, 0, 0),
    }
    return http.RawResponse(
        **fields, blocked=fetch._precheck_blocked(http.RawResponse(**fields))
    )


@pytest.mark.parametrize(
    ("answer", "usable"),
    [
        (_answer(200, "<div id=search>results</div>"), True),
        (_answer(200, "Our systems have detected unusual traffic"), False),
        (_answer(429, "too many"), False),
        (http.TransportError("Timeout", 28, 5000.0, "timed out"), False),
    ],
)
async def test_the_precheck_makes_one_bounded_attempt(monkeypatch, answer, usable):
    """GS-1: (5, 5) on the shared transport, which never retries; Scrapling's
    retries made a dead IP cost about 17 s."""
    sent: list[dict] = []

    async def request(method, url, **kw):
        sent.append(kw)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(fetch.http, "request", request)

    assert await fetch._precheck("https://www.google.com/search?q=pie", "p1") is usable
    assert len(sent) == 1
    assert sent[0]["timeout"] == (5.0, 5.0)
    assert sent[0]["proxy"] == "p1"
    assert sent[0]["cookies"] == fetch.CONSENT_COOKIES


@pytest.mark.parametrize(
    ("warm", "held", "slots"),
    [
        (0, {}, 1),
        (1, {}, 2),
        (2, {}, 4),
        (5, {}, 4),
        (1, {"p0": 1}, 1),
        (2, {"p0": 2, "p1": 2}, 1),
        (3, {"p0": 2, "p1": 1}, 3),
    ],
)
def test_render_slots_follow_the_warm_pool_s_free_slots(monkeypatch, warm, held, slots):
    """Two renders per warm IP less those other calls hold, at most the render
    gate (4); one when no warm slot is free, where every extra render would vet
    a fresh IP and likely pay a solve."""
    monkeypatch.setattr(fetch, "_MAX_CONCURRENT_PAGES", 4)
    monkeypatch.setattr(fetch, "_WARM_IP_MAX_CONCURRENCY", 2)
    monkeypatch.setattr(fetch, "_pool", {f"p{i}": 0.0 for i in range(warm)})
    monkeypatch.setattr(fetch, "_pool_inflight", dict(held))

    assert fetch.render_slots() == slots


def test_the_warm_up_launches_the_desktop_browser_and_closes_it_at_shutdown(
    monkeypatch,
):
    launched: list[bool] = []

    async def get_session(mobile):
        launched.append(mobile)

    monkeypatch.setattr(fetch, "AsyncStealthySession", object)
    monkeypatch.setattr(fetch, "_get_session", get_session)
    monkeypatch.setattr(lifecycle, "_closers", [])

    asyncio.run(fetch.warm_browser())

    assert launched == [False]
    assert lifecycle._closers == [fetch.close_sessions]


@pytest.mark.parametrize(("flag", "warms"), [("1", True), ("0", False)])
async def test_the_lifespan_warms_the_browser_unless_switched_off(
    monkeypatch, flag, warms
):
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", "account")
    server = importlib.import_module("proprietary.google_search.server")
    called = asyncio.Event()

    async def warm() -> None:
        called.set()

    monkeypatch.setattr(server, "warm_browser", warm)
    monkeypatch.setenv("GOOGLE_SEARCH_WARM_BROWSER", flag)

    async with server.lifespan():
        await asyncio.sleep(0.05)

    assert called.is_set() is warms


@pytest.mark.parametrize("ads", [False, True])
async def test_ad_hunting_renders_feed_no_prefetch(monkeypatch, ads):
    """focusOnPaidAds re-renders up to three times and throws the ad-less ones
    away, so their /goto waves would resolve links of pages never returned."""
    sinks: list[object] = []

    async def fetch_serp_html(url, *, mobile=False):
        sinks.append(fetch.link_sink.get())
        return (
            '<html><body><div id="rso"><div class="tF2Cxc">'
            '<a href="https://a.example/x"><h3>A</h3></a></div></div></body></html>'
        )

    monkeypatch.setattr(scraper, "PREFETCH", True)
    monkeypatch.setattr(scraper, "fetch_serp_html", fetch_serp_html)
    await scraper.scrape_serps(
        GoogleSearchScrapeInput(queries="pie", focusOnPaidAds=ads)
    )

    assert len(sinks) == (3 if ads else 1)
    assert all((sink is None) is ads for sink in sinks)


@pytest.fixture(scope="module")
def chromium():
    """A local Chromium with every request aborted; skipped when none is installed."""
    sync_playwright = pytest.importorskip("patchright.sync_api").sync_playwright

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as e:  # no browser installed here
            pytest.skip(f"no local Chromium: {e}")
        context = browser.new_context(java_script_enabled=False)
        context.route("**/*", lambda route: route.abort())
        yield context
        browser.close()


@pytest.mark.parametrize(
    "name",
    [
        "serp_best_running_shoes",
        "serp_climate_change",
        "serp_github",
        "serp_python",
        "serp_python_page2",
        "serp_site_ignored",
    ],
)
def test_the_render_feeds_exactly_the_links_the_parser_carries(chromium, name):
    """A SERP holds 64-109 distinct /goto links; resolving all of them would
    multiply the /goto load per page. The feed must match the parser's picks."""
    from proprietary.google_search import goto
    from proprietary.google_search.parsers import GOTO_PREFIX, parse_serp
    from proprietary.google_search.tests.test_serp_captures import capture

    html = capture(name)
    carried = {
        c.url
        for c in goto._url_carriers(parse_serp(html))
        if (c.url or "").startswith(GOTO_PREFIX)
    }
    page = chromium.new_page()
    try:
        page.set_content(html, wait_until="commit")
        fed = {
            GOTO_PREFIX + href.split("?", 1)[1]
            for href in page.evaluate(fetch._LINKS_JS, True)
        }
    finally:
        page.close()

    assert fed == carried
