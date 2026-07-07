"""``web.crawl`` I/O contract: camelCase surface, bounds, and billing counters."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.capabilities.web.crawl.schemas import (
    CrawlInput,
    CrawlItem,
    CrawlMeta,
    CrawlOutput,
)

pytestmark = pytest.mark.unit


def test_requires_at_least_one_start_url() -> None:
    with pytest.raises(ValidationError):
        CrawlInput(startUrls=[])


def test_camelcase_fields_and_defaults() -> None:
    model = CrawlInput(startUrls=["https://e.com"])
    assert model.startUrls == ["https://e.com"]
    assert model.maxCrawlDepth == 0
    assert model.maxCrawlPages == 10
    assert model.maxLength == 50_000


def test_depth_and_page_bounds_are_enforced() -> None:
    with pytest.raises(ValidationError):
        CrawlInput(startUrls=["https://e.com"], maxCrawlDepth=-1)
    with pytest.raises(ValidationError):
        CrawlInput(startUrls=["https://e.com"], maxCrawlDepth=99)
    with pytest.raises(ValidationError):
        CrawlInput(startUrls=["https://e.com"], maxCrawlPages=0)


def test_estimated_units_for_single_url_is_seed_count() -> None:
    model = CrawlInput(startUrls=["https://a.com", "https://b.com"], maxCrawlDepth=0)
    assert model.estimated_units == 2


def test_estimated_units_for_spider_is_max_pages() -> None:
    model = CrawlInput(startUrls=["https://a.com"], maxCrawlDepth=2, maxCrawlPages=25)
    assert model.estimated_units == 25


def test_billable_units_counts_only_successes() -> None:
    out = CrawlOutput(
        items=[
            CrawlItem(
                url="a", status="success", crawl=CrawlMeta(loadedUrl="a", depth=0)
            ),
            CrawlItem(url="b", status="empty", crawl=CrawlMeta(loadedUrl="b", depth=1)),
            CrawlItem(
                url="c", status="failed", crawl=CrawlMeta(loadedUrl="c", depth=1)
            ),
        ]
    )
    assert out.billable_units == 1


def test_captcha_counters_are_excluded_from_the_wire_shape() -> None:
    out = CrawlOutput(items=[], captcha_attempts=3, captcha_solved=1)
    dumped = out.model_dump()
    assert "captcha_attempts" not in dumped
    assert "captcha_solved" not in dumped
