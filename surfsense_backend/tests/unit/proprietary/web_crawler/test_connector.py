"""Unit tests for ``WebCrawlerConnector.crawl_url`` outcome semantics (Phase 3a).

These exercise the Scrapling tier ladder and the explicit ``CrawlOutcome``
contract that Phase 3c bills on, by stubbing the per-tier fetch helpers so the
ladder logic is tested deterministically without launching browsers/HTTP.
"""

import pytest

from app.proprietary.web_crawler import (
    CrawlOutcomeStatus,
    WebCrawlerConnector,
    connector as connector_module,
)
from app.utils.crawl import BlockType

pytestmark = pytest.mark.unit


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
        _url: str, _captcha_state: dict, block_state: dict
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

    class _Page:
        status = 403
        html_content = "<title>Just a moment...</title>"

    class _AsyncFetcher:
        @staticmethod
        async def get(*_a, **_k):
            return _Page()

    monkeypatch.setattr(connector_module, "AsyncFetcher", _AsyncFetcher)
    monkeypatch.setattr(connector_module, "get_proxy_url", lambda: None)

    block_state: dict = {"block_type": BlockType.UNKNOWN}
    result = await crawler._crawl_with_async_fetcher("https://example.com", block_state)

    assert result is None  # 4xx => fall through to next tier
    assert block_state["block_type"] is BlockType.CLOUDFLARE


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
