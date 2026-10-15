"""``crawl_url``'s ladder and ``CrawlOutcome``, with the per-tier fetches stubbed: no browser, no network."""

import asyncio
from pathlib import Path

import pytest

from proprietary.web_crawl import (
    CrawlOutcomeStatus,
    WebCrawlerConnector,
    net_guard,
)
from proprietary.web_crawl import (
    connector as connector_module,
)
from proprietary.web_crawl.classifier import BlockType


@pytest.fixture(autouse=True)
def _stub_destination_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the destination guard hermetic.

    ``crawl_url`` now resolves the target host before running a tier. These
    are unit tests, so the resolver answers with a fixed public address
    instead of whatever DNS says about ``example.com`` today.
    """
    monkeypatch.setattr(net_guard, "_resolve_host", lambda _host: ["93.184.216.34"])


def _result(tier: str) -> dict:
    return {
        "content": "hello world",
        "metadata": {"source": "https://example.com", "title": "Example"},
        "crawler_type": tier,
    }


async def test_invalid_url_is_failed() -> None:
    """A URL that fails validation never reaches a tier and is FAILED."""
    outcome = await WebCrawlerConnector().crawl_url("not a url")

    assert outcome.status is CrawlOutcomeStatus.FAILED
    assert outcome.result is None
    assert "Invalid URL" in (outcome.error or "")


async def test_static_tier_success_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Static success returns SUCCESS and never touches the browser tiers."""
    crawler = WebCrawlerConnector()
    later_calls: list[str] = []

    async def _static(_url: str, *_args) -> dict:
        return _result("scrapling-static")

    async def _record_dynamic(_url: str, *_args) -> None:
        later_calls.append("dynamic")
        return None

    async def _record_stealthy(_url: str, *_args) -> None:
        later_calls.append("stealthy")
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _static)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _record_dynamic)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _record_stealthy)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-static"
    assert outcome.result is not None
    assert outcome.result["crawler_type"] == "scrapling-static"
    assert later_calls == []


async def test_escalates_to_dynamic_on_static_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Static empty extraction escalates to the dynamic tier."""
    crawler = WebCrawlerConnector()

    async def _empty(_url: str, *_args) -> None:
        return None

    async def _dynamic(_url: str, *_args) -> dict:
        return _result("scrapling-dynamic")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _dynamic)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-dynamic"


def test_dropped_currency_amounts_detection() -> None:
    """Fires only when the DOM has currency figures that the markdown lost."""
    dropped = connector_module.dropped_currency_amounts
    html = "<html><body><div>Pro plan <b>$49</b>/mo</div></body></html>"
    assert dropped(html, "Pro plan without figures")
    assert not dropped(html, "Pro plan $49/mo")  # markdown kept it
    assert not dropped("<html><body>no prices here</body></html>", "text")
    # Country-agnostic: symbol-after-amount and ISO codes count too.
    assert dropped("<html><body>ab 49€ pro Monat</body></html>", "ab pro Monat")
    assert dropped("<html><body>USD 2,500 per year</body></html>", "per year")
    # Script content is not visible: a JSON payload price must not trigger.
    assert not dropped(
        "<html><body><script>{'price':'$9'}</script>hi</body></html>", "hi"
    )


def test_build_result_repairs_pricing_card_loss() -> None:
    """div-grid pricing cards dropped by trafilatura get recovered."""
    cards = "".join(
        f"<div class='col'><h3>{name}</h3><div class='price'>${price}</div>"
        f"<ul><li>feature a</li><li>feature b</li></ul>"
        f"<a href='/signup'>Choose {name}</a></div>"
        for name, price in (("Free", 0), ("Pro", 49), ("Enterprise", 199))
    )
    html = (
        "<html><head><title>Pricing</title></head><body>"
        "<article><h1>Simple pricing</h1><p>"
        + "Choose the plan that fits your team best. " * 30
        + "</p></article><section class='grid'>"
        + cards
        + "</section></body></html>"
    )
    result = WebCrawlerConnector()._build_result(
        html, "https://x.com/pricing", "t", allow_raw_fallback=False
    )
    assert result is not None
    assert "$49" in result["content"]
    assert "$199" in result["content"]


def test_looks_like_js_shell_thresholds() -> None:
    """Shell = huge HTML AND near-empty extraction; either alone is healthy."""
    shell = connector_module.looks_like_js_shell
    assert shell(4_200_000, 597)  # a16z.com/team
    assert not shell(200_000, 13_092)  # a16z investment-list: normal page
    assert not shell(45_000, 1_356)  # small brochure page: small is not thin
    assert not shell(4_200_000, 50_000)  # huge but content-rich (long article)


async def test_thin_static_shell_escalates_to_dynamic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JS-shell static result escalates; the hydrated dynamic result wins."""
    crawler = WebCrawlerConnector()

    async def _thin_static(_url: str, *_args) -> dict:
        return _result("scrapling-static") | {"thin_static": True}

    async def _dynamic(_url: str, *_args) -> dict:
        return _result("scrapling-dynamic")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _thin_static)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _dynamic)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-dynamic"


async def test_thin_static_is_fallback_when_browser_tiers_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser tiers unavailable -> the partial static content still returns."""
    crawler = WebCrawlerConnector()

    async def _thin_static(_url: str, *_args) -> dict:
        return _result("scrapling-static") | {"thin_static": True}

    async def _unavailable(_url: str, *_args) -> None:
        raise NotImplementedError("no subprocess support")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _thin_static)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _unavailable)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _unavailable)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-static"
    assert outcome.result is not None
    assert "thin_static" not in outcome.result  # internal tag never leaks


async def test_all_tiers_empty_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every tier fetched but extracted nothing -> EMPTY (not billable)."""
    crawler = WebCrawlerConnector()

    async def _empty(_url: str, *_args) -> None:
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _empty)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.EMPTY
    assert outcome.result is None


async def test_all_tiers_raise_is_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every tier raising (none reachable) -> FAILED with aggregated errors."""
    crawler = WebCrawlerConnector()

    async def _boom(_url: str, *_args) -> None:
        raise RuntimeError("fetch exploded")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _boom)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _boom)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _boom)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.FAILED
    assert "fetch exploded" in (outcome.error or "")


async def test_proxy_error_rotates_once_when_pool_backed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """03b: a pool-backed provider retries the tier once on a proxy error."""
    crawler = WebCrawlerConnector()
    calls = {"n": 0}

    async def _flaky(_url: str, *_args) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("connection refused by upstream proxy")
        return _result("scrapling-static")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _flaky)
    monkeypatch.setattr(connector_module, "is_pool_backed", lambda: True)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-static"
    assert calls["n"] == 2  # original attempt + one rotation retry


async def test_proxy_error_no_retry_when_single_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-endpoint providers skip the retry (no re-hit of the dead proxy)."""
    crawler = WebCrawlerConnector()
    static_calls = {"n": 0}

    async def _proxy_err(_url: str, *_args) -> None:
        static_calls["n"] += 1
        raise RuntimeError("connection refused by upstream proxy")

    async def _empty(_url: str, *_args) -> None:
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _proxy_err)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _empty)
    monkeypatch.setattr(connector_module, "is_pool_backed", lambda: False)

    outcome = await crawler.crawl_url("https://example.com")

    assert static_calls["n"] == 1  # no retry
    assert outcome.status is CrawlOutcomeStatus.EMPTY


async def test_captcha_defaults_zero_on_non_stealthy_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """03d: a static success never touches captcha → fields stay 0/False."""
    crawler = WebCrawlerConnector()

    async def _static(_url: str, *_args) -> dict:
        return _result("scrapling-static")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _static)
    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.captcha_attempts == 0
    assert outcome.captcha_solved is False


async def test_captcha_state_surfaced_onto_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """03d: the stealthy tier's captcha_state is stamped onto the outcome,
    even when the lower tiers missed and stealthy itself succeeds."""
    crawler = WebCrawlerConnector()

    async def _empty(_url: str, *_args) -> None:
        return None

    async def _stealthy(_url: str, captcha_state: dict, *_args) -> dict:
        # Simulate the page_action having solved a captcha mid-fetch.
        captcha_state["attempts"] = 2
        captcha_state["solved"] = True
        return _result("scrapling-stealthy")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _stealthy)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-stealthy"
    assert outcome.captcha_attempts == 2
    assert outcome.captcha_solved is True


async def test_captcha_attempts_surface_even_when_crawl_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """03d: attempts are billed per-attempt → must surface on a FAILED outcome."""
    crawler = WebCrawlerConnector()

    async def _empty(_url: str, *_args) -> None:
        return None

    async def _stealthy_attempt_then_empty(
        _url: str, captcha_state: dict, *_args
    ) -> None:
        captcha_state["attempts"] = 1  # solve attempted but crawl still empty
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _stealthy_attempt_then_empty)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.EMPTY
    assert outcome.captcha_attempts == 1
    assert outcome.captcha_solved is False


async def test_non_proxy_error_never_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-proxy error is not retried even when pool-backed."""
    crawler = WebCrawlerConnector()
    calls = {"n": 0}

    async def _boom(_url: str, *_args) -> None:
        calls["n"] += 1
        raise RuntimeError("totally unrelated failure")

    async def _empty(_url: str, *_args) -> None:
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _boom)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _empty)
    monkeypatch.setattr(connector_module, "is_pool_backed", lambda: True)

    outcome = await crawler.crawl_url("https://example.com")

    assert calls["n"] == 1  # not retried (not a proxy error)
    assert outcome.status is CrawlOutcomeStatus.EMPTY


async def test_invalid_url_block_type_defaults_unknown() -> None:
    """03e: a pre-fetch FAILED carries the default UNKNOWN block_type."""
    outcome = await WebCrawlerConnector().crawl_url("not a url")

    assert outcome.status is CrawlOutcomeStatus.FAILED
    assert outcome.block_type is BlockType.UNKNOWN


async def test_block_type_surfaced_onto_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """03e: a tier's block classification (in block_state) is stamped onto the
    outcome — additive only, never gating SUCCESS."""
    crawler = WebCrawlerConnector()

    async def _empty(_url: str, *_args) -> None:
        return None

    async def _stealthy_blocked(
        _url: str, _captcha_state: dict, block_state: dict, *_args
    ) -> None:
        # Simulate _build_result having classified a Cloudflare interstitial.
        block_state["block_type"] = BlockType.CLOUDFLARE
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _stealthy_blocked)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.EMPTY
    assert outcome.block_type is BlockType.CLOUDFLARE


def test_build_result_classifies_into_block_state() -> None:
    """03e: _build_result labels the fetched page into the passed block_state."""
    crawler = WebCrawlerConnector()
    block_state: dict = {"block_type": BlockType.UNKNOWN}

    cf_html = "<html><head><title>Just a moment...</title></head></html>"
    result = crawler._build_result(
        cf_html,
        "https://example.com",
        "scrapling-stealthy",
        allow_raw_fallback=False,
        status=403,
        block_state=block_state,
    )

    # Cloudflare interstitial: no real content extracted (None) but classified.
    assert result is None
    assert block_state["block_type"] is BlockType.CLOUDFLARE


async def test_static_4xx_is_classified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """03e: a static-tier 4xx bot-gate is classified before the early return
    (otherwise the cheapest/first tier's block signal would be lost)."""
    crawler = WebCrawlerConnector()

    _serve_static(monkeypatch, _FakePage(403, "<title>Just a moment...</title>"))

    block_state: dict = {"block_type": BlockType.UNKNOWN}
    result = await crawler._crawl_with_async_fetcher("https://example.com", block_state)

    assert result is None  # 4xx => fall through to next tier
    assert block_state["block_type"] is BlockType.CLOUDFLARE


class _FakeScrollPage:
    """Playwright-page stand-in: height grows per scroll until a plateau."""

    def __init__(self, heights: list[int]):
        self._heights = heights
        self._i = 0
        self.scrolls = 0

    async def evaluate(self, script: str):
        if "innerHeight" in script:
            return 800
        if "scrollHeight" in script and "scrollTo" not in script:
            return self._heights[min(self._i, len(self._heights) - 1)]
        self.scrolls += 1
        self._i += 1
        return None

    async def wait_for_timeout(self, _ms: int) -> None:
        pass


async def test_scroll_to_bottom_stops_when_height_stops_growing() -> None:
    page = _FakeScrollPage([1000, 2000, 3000, 3000])
    assert await connector_module.scroll_to_bottom(page) is page
    # Grew to 2000 and 3000, then two scrolls without growth ended it.
    assert page.scrolls == 4


async def test_scroll_to_bottom_skips_a_page_no_taller_than_the_window() -> None:
    page = _FakeScrollPage([700, 5000])
    await connector_module.scroll_to_bottom(page)
    assert page.scrolls == 0


async def test_scroll_to_bottom_waits_out_one_slow_lazy_load() -> None:
    """A loader that adds nothing on one round but does on the next is still read."""
    page = _FakeScrollPage([1000, 1000, 2000, 2000, 2000])
    await connector_module.scroll_to_bottom(page)
    assert page.scrolls == 4


async def test_scroll_to_bottom_is_bounded_on_endless_feeds() -> None:
    page = _FakeScrollPage([i * 1000 for i in range(1, 100)])  # never stabilizes
    await connector_module.scroll_to_bottom(page)
    assert page.scrolls == connector_module._SCROLL_MAX_ROUNDS


async def test_scroll_to_bottom_swallows_page_errors() -> None:
    class _Broken:
        async def evaluate(self, _script: str):
            raise RuntimeError("target closed")

    page = _Broken()
    assert await connector_module.scroll_to_bottom(page) is page  # never raises


def test_build_result_ok_on_real_content() -> None:
    """03e: a normal 200 page with content classifies OK."""
    crawler = WebCrawlerConnector()
    block_state: dict = {"block_type": BlockType.UNKNOWN}

    html = (
        "<html><body><article>" + ("Real content. " * 40) + "</article></body></html>"
    )
    crawler._build_result(
        html,
        "https://example.com",
        "scrapling-static",
        allow_raw_fallback=False,
        status=200,
        block_state=block_state,
    )

    assert block_state["block_type"] is BlockType.OK


async def test_restricted_url_is_failed_before_any_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A host that is not publicly routable never reaches a fetch tier.

    ``validators.url`` passes the cloud metadata endpoint, so without the
    destination guard this URL is fetched from inside the host's network.
    """
    crawler = WebCrawlerConnector()
    tiers: list[str] = []

    async def _record_static(_url: str, *_args) -> None:
        tiers.append("static")
        return None

    async def _record_dynamic(_url: str, *_args) -> None:
        tiers.append("dynamic")
        return None

    async def _record_stealthy(_url: str, *_args) -> None:
        tiers.append("stealthy")
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _record_static)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _record_dynamic)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _record_stealthy)

    outcome = await crawler.crawl_url("http://169.254.169.254/latest/meta-data/")

    assert outcome.status is CrawlOutcomeStatus.FAILED
    assert outcome.result is None
    assert "Restricted URL" in (outcome.error or "")
    assert tiers == []


async def test_restricted_url_is_reported_apart_from_a_malformed_one() -> None:
    """The two refusals are different diagnoses and must not share a message."""
    restricted = await WebCrawlerConnector().crawl_url("http://127.0.0.1:8000/health")
    malformed = await WebCrawlerConnector().crawl_url("not a url")

    assert "Restricted URL" in (restricted.error or "")
    assert "Invalid URL" in (malformed.error or "")
    assert (malformed.error or "") != (restricted.error or "")


# --- Routing on HTTP status and challenge walls ---------------------------

FIXTURES = Path(__file__).parent / "fixtures"

# A docs site's real "Page not found": its navigation alone is over 2 KB.
_NOT_FOUND_PAGE = (
    "<html><head><title>Page not found</title></head><body><nav>"
    + "".join(f'<a href="/3/library/m{i}.html">Module {i}</a> ' for i in range(80))
    + "</nav><main><h1>Page not found</h1><p>"
    + "The page you asked for does not exist. Try the search box or the index. " * 4
    + "</p></main></body></html>"
)
_CF_WALL = (
    "<html><head><title>Just a moment...</title></head><body>"
    "<h1>Performing security verification</h1>"
    "<p>This website uses a security service to protect against malicious bots."
    " Verify you are human.</p></body></html>"
)


class _FakePage:
    def __init__(self, status: int, html: str, url: str = "https://example.com"):
        self.status = status
        self.html_content = html
        self.url = url


def _fetched(page: _FakePage) -> connector_module._Fetched:
    return connector_module._Fetched(page.status, page.url, page.html_content)


def _serve_static(monkeypatch: pytest.MonkeyPatch, page: _FakePage) -> None:
    async def _fetch_static(_url: str) -> connector_module._Fetched:
        return _fetched(page)

    monkeypatch.setattr(connector_module, "_fetch_static", _fetch_static)


def _serve_dynamic(monkeypatch: pytest.MonkeyPatch, page: _FakePage) -> list[str]:
    """The dynamic tier's browser answers ``page``; returns the URLs it fetched.

    Serves both the pooled render and, behind its kill switch, Scrapling's.
    """
    fetched: list[str] = []

    async def _render_dynamic(url: str) -> connector_module._Fetched:
        fetched.append(url)
        return _fetched(page)

    async def _run_here(fn):
        return await fn()

    class _DynamicFetcher:
        @staticmethod
        async def async_fetch(url: str, **_k):
            fetched.append(url)
            return page

    async def _same_loop(coro):
        return await coro

    monkeypatch.setattr(connector_module, "_render_dynamic", _render_dynamic)
    monkeypatch.setattr(connector_module.browser_pool, "run", _run_here)
    monkeypatch.setattr(connector_module, "DynamicFetcher", _DynamicFetcher)
    monkeypatch.setattr(connector_module, "in_browser_loop", _same_loop)
    monkeypatch.setattr(connector_module, "get_proxy_url", lambda: None)
    return fetched


def _record_tiers(
    monkeypatch: pytest.MonkeyPatch, crawler: WebCrawlerConnector, *, dynamic: bool
) -> list[str]:
    tiers: list[str] = []

    async def _dynamic(_url: str, *_args) -> None:
        tiers.append("dynamic")

    async def _stealthy(_url: str, *_args) -> None:
        tiers.append("stealthy")

    if dynamic:
        monkeypatch.setattr(crawler, "_crawl_with_dynamic", _dynamic)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _stealthy)
    return tiers


async def test_static_404_page_fails_fast_without_a_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """c06: a real 404 page went through a 5 s browser render and came back SUCCESS."""
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(404, _NOT_FOUND_PAGE))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=True)

    outcome = await crawler.crawl_url("https://example.com/missing")

    assert outcome.status is CrawlOutcomeStatus.FAILED
    assert outcome.error == "HTTP 404 for https://example.com/missing"
    assert tiers == []


async def test_tiny_static_404_still_tries_a_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stub 404 may be a gate that only browsers pass."""
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(404, "<html><body>nope</body></html>"))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=True)

    outcome = await crawler.crawl_url("https://example.com/missing")

    assert tiers == ["dynamic", "stealthy"]
    assert "Scrapling static: HTTP 404;" in (outcome.error or "")


async def test_static_403_without_markers_still_escalates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(403, _NOT_FOUND_PAGE))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=True)

    await crawler.crawl_url("https://example.com/")

    assert tiers == ["dynamic", "stealthy"]


async def test_static_cloudflare_wall_goes_straight_to_stealth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """c07: the dynamic tier spent 18 s and returned the wall as the page."""
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(403, _CF_WALL))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=True)

    outcome = await crawler.crawl_url("https://example.com/")

    assert tiers == ["stealthy"]
    assert outcome.block_type is BlockType.CLOUDFLARE
    assert "skipped (cloudflare wall)" in (outcome.error or "")


async def test_dynamic_tier_404_ends_the_ladder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The browser rendered the site's own 404: stealth would get it too."""
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(404, "<html><body>nope</body></html>"))
    fetched = _serve_dynamic(monkeypatch, _FakePage(404, _NOT_FOUND_PAGE))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=False)

    outcome = await crawler.crawl_url("https://example.com/missing")

    assert fetched == ["https://example.com/missing"]
    assert tiers == []
    assert outcome.status is CrawlOutcomeStatus.FAILED
    assert outcome.error == "HTTP 404 for https://example.com/missing"


async def test_dynamic_tier_challenge_page_is_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 403 wall rendered by the browser escalates to stealth; nothing reads as the page."""
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(503, "<html><body>busy</body></html>"))
    _serve_dynamic(monkeypatch, _FakePage(403, _CF_WALL))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=False)

    outcome = await crawler.crawl_url("https://example.com/")

    assert tiers == ["stealthy"]
    assert outcome.status is not CrawlOutcomeStatus.SUCCESS
    assert "Scrapling dynamic: HTTP 403" in (outcome.error or "")


def test_build_result_rejects_a_200_interstitial() -> None:
    block_state: dict = {"block_type": BlockType.UNKNOWN}
    result = WebCrawlerConnector()._build_result(
        _CF_WALL,
        "https://example.com/",
        "scrapling-stealthy",
        allow_raw_fallback=True,
        status=200,
        block_state=block_state,
    )
    assert result is None
    assert block_state["blocked"] is True


def test_build_result_keeps_a_long_page_that_embeds_turnstile() -> None:
    """A signup form's Turnstile widget is no wall: the page has content."""
    html = (
        "<html><body><article><h1>Sign up</h1><p>"
        + "Create an account to keep your notes in sync across devices. " * 30
        + '</p><div class="cf-turnstile"></div></article></body></html>'
    )
    result = WebCrawlerConnector()._build_result(
        html, "https://example.com/", "scrapling-static", allow_raw_fallback=False
    )
    assert result is not None


async def test_routing_kill_switch_restores_the_old_ladder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEB_CRAWL_STATUS_ROUTING", "0")
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(404, _NOT_FOUND_PAGE))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=True)

    outcome = await crawler.crawl_url("https://example.com/missing")

    assert tiers == ["dynamic", "stealthy"]
    assert outcome.status is CrawlOutcomeStatus.EMPTY


# --- Redirects ---------------------------------------------------------------


async def test_links_resolve_against_the_url_after_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """c08: the domain root redirects to /en/latest/; its relative links were
    resolved against the root and all pointed at 404s."""
    html = (
        "<html><body><article><h1>Requests</h1><p>"
        + "Requests is an elegant and simple HTTP library for Python. " * 20
        + '</p><a href="user/install/">Install</a></article></body></html>'
    )
    crawler = WebCrawlerConnector()
    _serve_static(
        monkeypatch,
        _FakePage(200, html, url="https://requests.readthedocs.io/en/latest/"),
    )

    outcome = await crawler.crawl_url("https://requests.readthedocs.io")

    assert outcome.result is not None
    assert outcome.result["loaded_url"] == "https://requests.readthedocs.io/en/latest/"
    assert outcome.result["links"] == [
        "https://requests.readthedocs.io/en/latest/user/install/"
    ]


# --- Extraction: cap, one parse, data fixes --------------------------------


def _article_page(sections: int) -> str:
    body = "".join(
        f"<section><h2>Release {i}</h2><p>"
        + f"Fixed issue {i} in the parser and the scheduler, with tests. " * 12
        + f'</p><ul><li><a href="/issues/{i}">Issue {i}</a></li></ul></section>'
        for i in range(sections)
    )
    return (
        "<html><head><title>Changelog</title></head>"
        f"<body><article>{body}</article></body></html>"
    )


def test_cap_html_cuts_at_a_tag_end(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connector_module, "_HTML_CAP_FLOOR", 100)
    html = "<p>" + "a" * 60 + "</p><p>" + "b" * 60 + "</p>"
    assert connector_module.cap_html(html, None) == "<p>" + "a" * 60 + "</p><p>"
    assert connector_module.cap_html(html, 10) == html  # 20 x max_length covers it
    monkeypatch.setenv("WEB_CRAWL_HTML_CAP", "0")
    assert connector_module.cap_html(html, None) == html


def test_capped_extraction_keeps_the_uncapped_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cap must not change what the caller keeps: the first max_length chars."""
    html = _article_page(1500)  # about 1.4 MB
    crawler = WebCrawlerConnector()
    limits = connector_module.PageLimits(max_length=3000)

    capped = crawler._build_result(
        html, "https://e.com/", "t", allow_raw_fallback=False, limits=limits
    )
    monkeypatch.setenv("WEB_CRAWL_HTML_CAP", "0")
    whole = crawler._build_result(
        html, "https://e.com/", "t", allow_raw_fallback=False, limits=limits
    )

    assert capped is not None and whole is not None
    assert len(capped["content"]) < len(whole["content"])
    assert capped["content"][:3000] == whole["content"][:3000]
    # Links past the cap still reach the crawl frontier.
    assert "https://e.com/issues/1499" in capped["links"]


def test_a_capped_page_s_emails_are_read_from_the_whole_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 7 MB changelog's emails sat between the cap and the footer: all were lost."""
    monkeypatch.setattr(connector_module, "_HTML_CAP_FLOOR", 2000)
    monkeypatch.setattr(connector_module, "_CONTACTS_TAIL_CHARS", 500)
    filler = "<p>" + "Release notes for the next version. " * 30 + "</p>"
    html = (
        "<html><body><article><h1>Changelog</h1>"
        + filler * 3
        + "<p>Thanks to dev&#64;middle.example for the fix.</p>"
        + filler * 3
        + '<footer><a href="mailto:press@tail.example">Press</a></footer>'
        + "</article></body></html>"
    )

    result = WebCrawlerConnector()._build_result(
        html, "https://e.com/", "t", allow_raw_fallback=False
    )

    assert result is not None
    assert result["contacts"]["emails"] == ["dev@middle.example", "press@tail.example"]


def test_build_result_parses_the_page_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Extraction, metadata, the currency check, links and contacts each
    parsed the whole page; now one parse feeds them all."""
    loads = {"n": 0}
    real_load = connector_module.load_html

    def counting_load(html):
        loads["n"] += 1
        return real_load(html)

    def no_fromstring(*_a, **_k):
        raise AssertionError("the page was parsed again")

    monkeypatch.setattr(connector_module, "load_html", counting_load)
    monkeypatch.setattr(connector_module.lxml_html, "fromstring", no_fromstring)
    html = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")

    result = WebCrawlerConnector()._build_result(
        html, "https://docs.python.org/3/tutorial/", "t", allow_raw_fallback=False
    )

    assert result is not None
    assert loads["n"] == 1


def test_build_result_classifies_only_the_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[int] = []

    def recording_classify(_status, html):
        seen.append(len(html or ""))
        return BlockType.OK

    monkeypatch.setattr(connector_module, "classify_block", recording_classify)
    WebCrawlerConnector()._build_result(
        _article_page(200), "https://e.com/", "t", allow_raw_fallback=False
    )
    assert seen == [connector_module._CLASSIFY_HEAD_CHARS]


def test_sphinx_permalinks_leave_headings() -> None:
    """'# The Python Tutorial[¶](#the-python-tutorial)' read as a heading."""
    html = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")
    result = WebCrawlerConnector()._build_result(
        html, "https://docs.python.org/3/tutorial/", "t", allow_raw_fallback=False
    )
    assert result is not None
    assert result["content"].startswith("# The Python Tutorial\n")
    assert "¶" not in result["content"]


def test_mkdocs_title_loses_its_pilcrow_and_date_is_the_latest() -> None:
    """fastapi release notes: title 'Release Notes¶', and date 2011-06-01,
    the oldest date on a page whose latest release is 2026-10-08."""
    html = (FIXTURES / "fastapi_release_notes.html").read_text(encoding="utf-8")
    result = WebCrawlerConnector()._build_result(
        html,
        "https://fastapi.tiangolo.com/release-notes/",
        "t",
        allow_raw_fallback=False,
    )
    assert result is not None
    assert result["metadata"]["title"] == "Release Notes"
    assert result["metadata"]["date"] == "2026-10-08"


def test_a_page_without_a_dated_markup_is_dated_by_its_footer() -> None:
    """docs.python.org dates a page only in "Last updated on Oct 14, 2026"."""
    html = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")
    result = WebCrawlerConnector()._build_result(
        html,
        "https://docs.python.org/3/tutorial/index.html",
        "t",
        allow_raw_fallback=False,
    )
    assert result is not None
    assert result["metadata"]["date"] == "2026-10-14"


def test_stealth_fallback_is_markdown_never_raw_html() -> None:
    """The last tier returned the whole HTML document in the markdown field."""
    html = (
        "<html><head><script>var tracking = 1;</script></head><body>"
        '<nav><a href="/a">Alpha</a> <a href="/b">Beta</a></nav></body></html>'
    )
    result = WebCrawlerConnector()._build_result(
        html, "https://e.com/", "scrapling-stealthy", allow_raw_fallback=True
    )
    assert result is not None
    assert "<html" not in result["content"]
    assert "Alpha" in result["content"]
    assert "tracking" not in result["content"]


def test_link_records_are_capped_and_counted() -> None:
    limits = connector_module.PageLimits(max_links=50)
    result = WebCrawlerConnector()._build_result(
        _article_page(300),
        "https://e.com/",
        "t",
        allow_raw_fallback=False,
        limits=limits,
    )
    assert result is not None
    assert len(result["link_records"]) == 50
    assert result["links_total"] == 300
    assert len(result["links"]) == 300  # the frontier is not capped


# --- the static tier on the shared transport (WC-6) ---------------------------


async def test_static_fetch_decodes_with_the_charset_and_reports_the_final_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real socket on 127.0.0.1: a latin-1 page, and a redirect's landing URL."""
    from proprietary.scraping.tests._local_http import LocalServer

    monkeypatch.setattr(connector_module.sessions.Exit, "proxy_url", lambda _s: None)
    async with LocalServer() as server:
        latin = await connector_module._fetch_static(f"{server.base}/latin")
        moved = await connector_module._fetch_static(f"{server.base}/redirect")
        sent = server.requests[0]["headers"]

    assert (latin.status, latin.html) == (200, "café")
    assert (moved.status, moved.url, moved.html) == (200, f"{server.base}/ok", "hello")
    # The one header Scrapling's stealthy_headers added.
    assert sent.get("referer") == "https://www.google.com/"


async def test_static_fetch_tries_a_fresh_exit_once_after_a_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead exit that never answers costs two short tries, not Scrapling's 20 s."""
    from proprietary.scraping.http import TransportError
    from proprietary.scraping.tests._local_http import Blackhole

    monkeypatch.setattr(connector_module, "_STATIC_TIMEOUT", (0.3, 0.3))
    async with Blackhole() as hole:
        monkeypatch.setattr(
            connector_module.sessions.Exit, "proxy_url", lambda _s: hole.proxy
        )
        with pytest.raises(TransportError) as raised:
            await connector_module._fetch_static("http://example.com/")
        connections = hole.connections

    assert raised.value.kind == "Timeout"
    assert connections == 2


def _failing_transport(
    monkeypatch: pytest.MonkeyPatch, kind: str, code: int, elapsed_ms: float
) -> list[int]:
    """``http.request`` failing every attempt with ``kind``; returns the attempts."""
    from proprietary.scraping.http import TransportError

    attempts: list[int] = []

    async def _failing(*_a, attempt: int = 0, **_k):
        attempts.append(attempt)
        raise TransportError(kind, code, elapsed_ms, "failed")

    monkeypatch.setattr(connector_module.http, "request", _failing)
    return attempts


@pytest.mark.parametrize(("kind", "code"), [("ProxyError", 56), ("ConnectionError", 7)])
async def test_static_fetch_tries_a_fresh_exit_once_after_a_bad_exit(
    monkeypatch: pytest.MonkeyPatch, kind: str, code: int
) -> None:
    """A refused tunnel is the exit's fault: Scrapling retried these, and a
    browser render costs seconds and one of the plugin's two pool slots."""
    from proprietary.scraping.http import TransportError

    attempts = _failing_transport(monkeypatch, kind, code, 40.0)
    with pytest.raises(TransportError):
        await connector_module._fetch_static("https://example.com/")
    assert attempts == [0, 1]


async def test_static_fetch_does_not_retry_a_slow_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timeout past the connect phase is a slow site: the browser goes next."""
    from proprietary.scraping.http import TransportError

    attempts = _failing_transport(monkeypatch, "Timeout", 28, 10_000.0)
    with pytest.raises(TransportError):
        await connector_module._fetch_static("https://example.com/")
    assert attempts == [0]


async def test_static_fetch_does_not_retry_other_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from proprietary.scraping.http import TransportError

    attempts = _failing_transport(monkeypatch, "SSLError", 35, 300.0)
    with pytest.raises(TransportError):
        await connector_module._fetch_static("https://example.com/")
    assert attempts == [0]


async def test_static_fetch_kill_switch_goes_back_to_scrapling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEB_CRAWL_RAW_STATIC", "0")
    calls: list[dict] = []

    class _AsyncFetcher:
        @staticmethod
        async def get(url: str, **kwargs):
            calls.append(kwargs)
            return _FakePage(200, "<p>old</p>", url + "#landed")

    async def _no_transport(*_a, **_k):
        raise AssertionError("the transport must not be used")

    monkeypatch.setattr(connector_module, "AsyncFetcher", _AsyncFetcher)
    monkeypatch.setattr(connector_module, "get_proxy_url", lambda: None)
    monkeypatch.setattr(connector_module.http, "request", _no_transport)

    page = await connector_module._fetch_static("https://example.com/")

    assert (page.status, page.url, page.html) == (
        200,
        "https://example.com/#landed",
        "<p>old</p>",
    )
    assert calls[0]["timeout"] == 20


# --- the dynamic tier in the shared browser pool (WC-7) -----------------------


class _PoolPage:
    def __init__(self, html: str, url: str) -> None:
        self._html = html
        self.url = url
        self.scroll_reads = 0

    async def evaluate(self, script: str):
        self.scroll_reads += 1
        return 500  # no taller than the window: no scroll

    async def wait_for_timeout(self, _ms: int) -> None:
        pass


class _Pooled:
    def __init__(self, page: _PoolPage) -> None:
        self.page = page
        self.burned: str | None = None

    def burn(self, reason: str) -> None:
        self.burned = reason


def _fake_pool(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    html: str,
    url: str,
    landed: str | None = None,
) -> dict:
    """``browser_pool.page`` and ``settle`` stand-ins; returns what they were asked.

    The document answered at ``landed`` (the URL asked for by default) and
    the page ended at ``url``.
    """
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    seen: dict = {}
    pooled = _Pooled(_PoolPage(html, url))

    @asynccontextmanager
    async def page(plugin, profile, **kwargs):
        seen.update(plugin=plugin, profile=profile, **kwargs)
        yield pooled
        seen["burned"] = pooled.burned

    async def goto(_page, target, **kwargs):
        seen.update(goto=target, goto_kwargs=kwargs)
        response = SimpleNamespace(url=landed or target)
        return SimpleNamespace(status=status, headers={}, response=response)

    async def page_content(p):
        return p._html

    monkeypatch.setattr(connector_module.browser_pool, "page", page)
    monkeypatch.setattr(connector_module.settle, "goto", goto)
    monkeypatch.setattr(connector_module.settle, "page_content", page_content)
    return seen


async def test_dynamic_render_runs_in_the_pool_on_a_sticky_lease(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _fake_pool(monkeypatch, 200, "<p>rendered</p>", "https://example.com/landed")

    page = await connector_module._render_dynamic("https://example.com/")

    assert (page.status, page.url, page.html) == (
        200,
        "https://example.com/landed",
        "<p>rendered</p>",
    )
    assert seen["plugin"] == "web-crawl"
    assert seen["proxy"] is connector_module._lease
    assert seen["timeout_ms"] == 15_000
    assert seen["goto_kwargs"]["wait_until"] == "domcontentloaded"
    assert seen["goto_kwargs"]["idle_cap_ms"] == 3_000
    assert seen["goto_kwargs"]["referer"] == "https://www.google.com/"
    assert seen["profile"].block_webrtc is True
    assert seen["burned"] is None


async def test_dynamic_render_burns_the_exit_on_a_wall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _fake_pool(monkeypatch, 403, _CF_WALL, "https://example.com/")

    page = await connector_module._render_dynamic("https://example.com/")

    assert page.status == 403
    assert seen["burned"] == "HTTP 403"


async def test_dynamic_render_names_an_interstitial_as_such(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 200 Cloudflare wall burned as "HTTP 200" misled the block-rate count."""
    seen = _fake_pool(monkeypatch, 200, _CF_WALL, "https://example.com/")

    await connector_module._render_dynamic("https://example.com/")

    assert seen["burned"] == "interstitial"


async def test_dynamic_render_keeps_the_exit_on_a_gateway_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 502 is the origin's, not the exit's."""
    seen = _fake_pool(monkeypatch, 502, _NOT_FOUND_PAGE, "https://example.com/")

    page = await connector_module._render_dynamic("https://example.com/")

    assert page.status == 502
    assert seen["burned"] is None


async def test_dynamic_render_reads_a_spa_404_fallback_as_its_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub Pages serves a 404.html that sends the browser on to the app."""
    article = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")
    _fake_pool(monkeypatch, 404, article, "https://example.com/?p=/guide")

    async def _run_here(fn):
        return await fn()

    monkeypatch.setattr(connector_module.browser_pool, "run", _run_here)

    page = await connector_module._render_dynamic("https://example.com/guide")
    result = await WebCrawlerConnector()._crawl_with_dynamic(
        "https://example.com/guide", {"block_type": BlockType.UNKNOWN}
    )

    assert page.status is None
    assert result is not None


async def test_dynamic_render_keeps_a_404_that_stayed_put(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_pool(monkeypatch, 404, _NOT_FOUND_PAGE, "https://example.com/gone#top")

    page = await connector_module._render_dynamic("https://example.com/gone")

    assert page.status == 404


async def test_a_gateway_error_page_still_tries_a_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CDN's passing 502, even with a full error page, is no final answer."""
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(502, _NOT_FOUND_PAGE))
    tiers = _record_tiers(monkeypatch, crawler, dynamic=True)

    await crawler.crawl_url("https://example.com/")

    assert tiers == ["dynamic", "stealthy"]


class _CountingLauncher:
    """A browser launch that takes a moment and counts how many run at once."""

    def __init__(self, page: _FakePage) -> None:
        self.page = page
        self.running = 0
        self.peak = 0

    async def async_fetch(self, _url: str, **_kwargs) -> _FakePage:
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await asyncio.sleep(0.02)
            return self.page
        finally:
            self.running -= 1


async def test_stealth_launches_are_capped_across_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Cloudflare site crawled six pages at once launched six stealth browsers."""
    article = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")
    launcher = _CountingLauncher(_FakePage(200, article))

    async def _same_loop(coro):
        return await coro

    _serve_static(monkeypatch, _FakePage(403, _CF_WALL))
    monkeypatch.setattr(connector_module, "StealthyFetcher", launcher)
    monkeypatch.setattr(connector_module, "in_browser_loop", _same_loop)
    monkeypatch.setattr(connector_module, "get_proxy_url", lambda: None)
    monkeypatch.setattr(connector_module, "captcha_enabled", lambda: False)
    monkeypatch.setattr(connector_module, "_launch_gate", None)
    crawler = WebCrawlerConnector()

    outcomes = await asyncio.gather(
        *(crawler.crawl_url(f"https://example.com/{i}") for i in range(6))
    )

    assert {outcome.tier for outcome in outcomes} == {"scrapling-stealthy"}
    assert launcher.peak == connector_module._LAUNCH_CAP == 2


async def test_unpooled_dynamic_launches_are_capped_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEB_CRAWL_BROWSER_POOL", "0")
    article = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")
    _serve_dynamic(monkeypatch, _FakePage(200, article))
    launcher = _CountingLauncher(_FakePage(200, article))
    monkeypatch.setattr(connector_module, "DynamicFetcher", launcher)
    monkeypatch.setattr(connector_module, "_launch_gate", None)
    crawler = WebCrawlerConnector()

    await asyncio.gather(
        *(crawler._crawl_with_dynamic(f"https://example.com/{i}") for i in range(5))
    )

    assert launcher.peak == 2


async def test_dynamic_tier_kill_switch_launches_scrapling_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WEB_CRAWL_BROWSER_POOL", "0")
    article = (FIXTURES / "python_tutorial.html").read_text(encoding="utf-8")
    fetched = _serve_dynamic(monkeypatch, _FakePage(200, article))
    rendered: list[str] = []

    async def _render_dynamic(url: str):
        rendered.append(url)

    monkeypatch.setattr(connector_module, "_render_dynamic", _render_dynamic)

    result = await WebCrawlerConnector()._crawl_with_dynamic("https://example.com/")

    assert fetched == ["https://example.com/"]
    assert rendered == []
    assert result is not None


async def test_each_tier_is_announced_as_it_starts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    crawler = WebCrawlerConnector()
    _serve_static(monkeypatch, _FakePage(403, _NOT_FOUND_PAGE))
    _record_tiers(monkeypatch, crawler, dynamic=True)
    heard: list[str] = []

    async def on_tier(tier: str) -> None:
        heard.append(tier)

    await crawler.crawl_url("https://example.com/", None, on_tier)

    assert heard == ["static fetch", "browser render", "stealth browser"]
