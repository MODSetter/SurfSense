"""Offline orchestration tests: pagination, dedupe, and caps via a fake session."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import pytest

from app.proprietary.platforms.indeed_jobs.schemas import IndeedScrapeInput
from app.proprietary.platforms.indeed_jobs.scraper import iter_indeed, scrape_indeed


def _page_html(job_keys: list[str]) -> str:
    """Wrap job keys in the ``mosaic-provider-jobcards`` assignment shape."""
    results = [
        {"jobkey": k, "displayTitle": f"Job {k}", "company": "Acme"} for k in job_keys
    ]
    model = {"metaData": {"mosaicProviderJobCardsModel": {"results": results}}}
    return (
        f'window.mosaic.providerData["mosaic-provider-jobcards"]={json.dumps(model)};'
    )


class _FakeSession:
    """Returns per-``start`` pages and records the URLs requested."""

    def __init__(self, pages: dict[int, list[str]]) -> None:
        self._pages = pages
        self.fetched: list[str] = []

    async def fetch_html(self, url: str) -> str:
        self.fetched.append(url)
        start = int(parse_qs(urlparse(url).query).get("start", ["0"])[0])
        return _page_html(self._pages.get(start, []))


async def _collect(input_model, session) -> list[dict]:
    return [item async for item in iter_indeed(input_model, session)]


@pytest.mark.asyncio
async def test_paginates_and_dedupes_across_pages():
    session = _FakeSession({0: ["k1", "k2", "k3"], 10: ["k3", "k4"], 20: []})
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100), session
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2", "k3", "k4"]
    assert all(i["scrapedAt"] for i in items)  # stamped by the orchestrator


@pytest.mark.asyncio
async def test_stops_when_a_page_is_all_duplicates():
    session = _FakeSession({0: ["k1", "k2"], 10: ["k1", "k2"], 20: ["k9"]})
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100), session
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
    assert 20 not in {
        int(parse_qs(urlparse(u).query).get("start", ["0"])[0]) for u in session.fetched
    }


@pytest.mark.asyncio
async def test_respects_max_items_per_query():
    session = _FakeSession({0: ["k1", "k2", "k3", "k4"]})
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=2), session
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]


@pytest.mark.asyncio
async def test_global_dedupe_across_queries():
    # Both queries hit page 0 (same fake pages) and return the same keys.
    session = _FakeSession({0: ["k1", "k2"]})
    items = await _collect(
        IndeedScrapeInput(queries=["dev", "engineer"], maxItemsPerQuery=100), session
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]


@pytest.mark.asyncio
async def test_start_urls_skip_viewjob_and_scrape_search():
    session = _FakeSession({0: ["k1"]})
    input_model = IndeedScrapeInput(
        startUrls=[
            {"url": "https://www.indeed.com/jobs?q=dev"},
            {"url": "https://www.indeed.com/viewjob?jk=abc"},
        ],
        maxItemsPerQuery=100,
    )
    items = await _collect(input_model, session)
    assert [i["jobKey"] for i in items] == ["k1"]


@pytest.mark.asyncio
async def test_scrape_indeed_limit_with_injected_session():
    session = _FakeSession({0: ["k1", "k2", "k3"]})
    items = await scrape_indeed(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100),
        limit=2,
        session=session,
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
