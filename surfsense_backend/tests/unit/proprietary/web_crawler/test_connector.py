"""Unit tests for ``WebCrawlerConnector.crawl_url`` outcome semantics (Phase 3a).

These exercise the Scrapling tier ladder and the explicit ``CrawlOutcome``
contract that Phase 3c bills on, by stubbing the per-tier fetch helpers so the
ladder logic is tested deterministically without launching browsers/HTTP.
"""

import pytest

from app.proprietary.web_crawler import (
    CrawlOutcomeStatus,
    WebCrawlerConnector,
)
from app.proprietary.web_crawler import connector as connector_module

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

    async def _static(_url: str) -> dict:
        return _result("scrapling-static")

    async def _record_dynamic(_url: str) -> None:
        later_calls.append("dynamic")
        return None

    async def _record_stealthy(_url: str) -> None:
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

    async def _empty(_url: str) -> None:
        return None

    async def _dynamic(_url: str) -> dict:
        return _result("scrapling-dynamic")

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _dynamic)

    outcome = await crawler.crawl_url("https://example.com")

    assert outcome.status is CrawlOutcomeStatus.SUCCESS
    assert outcome.tier == "scrapling-dynamic"


async def test_all_tiers_empty_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every tier fetched but extracted nothing -> EMPTY (not billable)."""
    crawler = WebCrawlerConnector()

    async def _empty(_url: str) -> None:
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

    async def _boom(_url: str) -> None:
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

    async def _flaky(_url: str) -> dict:
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

    async def _proxy_err(_url: str) -> None:
        static_calls["n"] += 1
        raise RuntimeError("connection refused by upstream proxy")

    async def _empty(_url: str) -> None:
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _proxy_err)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _empty)
    monkeypatch.setattr(connector_module, "is_pool_backed", lambda: False)

    outcome = await crawler.crawl_url("https://example.com")

    assert static_calls["n"] == 1  # no retry
    assert outcome.status is CrawlOutcomeStatus.EMPTY


async def test_non_proxy_error_never_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-proxy error is not retried even when pool-backed."""
    crawler = WebCrawlerConnector()
    calls = {"n": 0}

    async def _boom(_url: str) -> None:
        calls["n"] += 1
        raise RuntimeError("totally unrelated failure")

    async def _empty(_url: str) -> None:
        return None

    monkeypatch.setattr(crawler, "_crawl_with_async_fetcher", _boom)
    monkeypatch.setattr(crawler, "_crawl_with_dynamic", _empty)
    monkeypatch.setattr(crawler, "_crawl_with_stealthy", _empty)
    monkeypatch.setattr(connector_module, "is_pool_backed", lambda: True)

    outcome = await crawler.crawl_url("https://example.com")

    assert calls["n"] == 1  # not retried (not a proxy error)
    assert outcome.status is CrawlOutcomeStatus.EMPTY
