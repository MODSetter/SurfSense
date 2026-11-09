"""Offline orchestration tests: pagination, dedupe, and caps via a fake session."""

from __future__ import annotations

import asyncio
import json
from urllib.parse import parse_qs, urlparse

import pytest

from proprietary.indeed import scraper
from proprietary.indeed.fetch import Fetched, IndeedAccessBlockedError
from proprietary.indeed.parsers import extract_initial_data
from proprietary.indeed.schemas import IndeedScrapeInput
from proprietary.indeed.scraper import iter_indeed, scrape_indeed


def _page_html(job_keys: list[str]) -> str:
    """Wrap job keys in the ``mosaic-provider-jobcards`` assignment shape."""
    results = [
        {"jobkey": k, "displayTitle": f"Job {k}", "company": "Acme"} for k in job_keys
    ]
    model = {"metaData": {"mosaicProviderJobCardsModel": {"results": results}}}
    return (
        f'window.mosaic.providerData["mosaic-provider-jobcards"]={json.dumps(model)};'
    )


def _detail_html(job_key: str) -> str:
    """A minimal /viewjob page carrying a full description for ``job_key``."""
    data = {
        "jobInfoWrapperModel": {
            "jobInfoModel": {
                "sanitizedJobDescription": f"<div>Full description for {job_key}</div>",
                "jobInfoHeaderModel": {"jobTitle": f"Detailed {job_key}"},
            }
        }
    }
    return f"<html><script>window._initialData = {json.dumps(data)};</script></html>"


class _FakeSession:
    """Returns per-``start`` search pages (or a /viewjob detail) and records URLs.

    A page's details are the ``details_for`` keys, each answered from the
    ``details`` HTML for it (a page with no model gives none).
    """

    def __init__(
        self,
        pages: dict[int, list[str]],
        blocked_starts: set[int] | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        self._pages = pages
        self._blocked = blocked_starts or set()
        self._details = details or {}
        self.fetched: list[str] = []

        self.spa_requests: list[str] = []

    def _model(self, jk: str) -> dict | None:
        return extract_initial_data(self._details.get(jk) or _detail_html(jk))

    async def fetch_page(self, url: str, *, details_for=None, max_rotations=None):
        self.fetched.append(url)
        query = parse_qs(urlparse(url).query)
        start = int(query.get("start", ["0"])[0])
        if start in self._blocked:
            raise IndeedAccessBlockedError(f"gated at start={start}")
        html = _page_html(self._pages.get(start, []))
        wanted = details_for(html) if details_for else {}
        self.spa_requests.extend(wanted.values())
        models = {jk: self._model(jk) for jk in wanted}
        return Fetched(html, {jk: m for jk, m in models.items() if m is not None})

    async def fetch_job(self, url: str, job_key: str) -> dict | None:
        self.fetched.append(url)
        return self._model(job_key)


async def _collect(input_model, session) -> list[dict]:
    return [item async for item in iter_indeed(input_model, session)]


@pytest.mark.asyncio
async def test_dedupes_within_page():
    session = _FakeSession({0: ["k1", "k2", "k2", "k3"]})
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100), session
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2", "k3"]
    assert all(i["scrapedAt"] for i in items)  # stamped by the orchestrator


@pytest.mark.asyncio
async def test_does_not_fetch_deeper_pages():
    # First page only; ``start>=10`` must never be requested.
    session = _FakeSession({0: ["k1", "k2"], 10: ["k3"]})
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100), session
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
    assert all("start=" not in u for u in session.fetched)


@pytest.mark.asyncio
async def test_page_block_propagates():
    # Nothing yielded before the block, so it surfaces as an error.
    session = _FakeSession({}, blocked_starts={0})
    with pytest.raises(IndeedAccessBlockedError):
        await _collect(IndeedScrapeInput(queries=["dev"]), session)


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
async def test_start_urls_scrape_search_and_job_url_detail():
    session = _FakeSession({0: ["k1"]})
    input_model = IndeedScrapeInput(
        startUrls=[
            {"url": "https://www.indeed.com/jobs?q=dev"},
            {"url": "https://www.indeed.com/viewjob?jk=abc"},
        ],
        maxItemsPerQuery=100,
    )
    items = await _collect(input_model, session)
    assert len(items) == 2
    search_item, job_item = items
    assert search_item["jobKey"] == "k1"
    # The /viewjob URL is scraped from its detail page alone.
    assert job_item["jobUrl"].endswith("jk=abc")
    assert job_item["title"] == "Detailed abc"
    assert "Full description for abc" in job_item["descriptionText"]


@pytest.mark.asyncio
async def test_scrape_job_details_enriches_listing_items():
    session = _FakeSession({0: ["k1", "k2"]})
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100, scrapeJobDetails=True),
        session,
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
    for it in items:
        assert it["descriptionHtml"].startswith("<div>Full description for")
        assert "Full description for" in it["descriptionText"]
    # Asked from the search page itself (spa=1), not as page loads.
    assert session.spa_requests == ["/viewjob?jk=k1&spa=1", "/viewjob?jk=k2&spa=1"]
    assert session.fetched == ["https://www.indeed.com/jobs?q=dev"]


@pytest.mark.asyncio
async def test_scrape_indeed_limit_with_injected_session():
    session = _FakeSession({0: ["k1", "k2", "k3"]})
    items = await scrape_indeed(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100),
        limit=2,
        session=session,
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2"]


@pytest.mark.asyncio
async def test_scrape_indeed_tells_on_item_the_running_count():
    session = _FakeSession({0: ["k1", "k2", "k3"]})
    heard: list[int] = []

    async def on_item(count: int) -> None:
        heard.append(count)

    await scrape_indeed(
        IndeedScrapeInput(queries=["dev"], maxItemsPerQuery=100),
        session=session,
        on_item=on_item,
    )
    assert heard == [1, 2, 3]


@pytest.mark.asyncio
async def test_job_url_item_carries_its_job_key_and_a_clean_url():
    session = _FakeSession({})
    input_model = IndeedScrapeInput(
        startUrls=[{"url": "https://www.indeed.com/viewjob?jk=abc&from=serp&tk=t0k"}]
    )
    [item] = await _collect(input_model, session)
    assert item["jobKey"] == "abc"
    assert item["jobUrl"] == "https://www.indeed.com/viewjob?jk=abc"


@pytest.mark.asyncio
async def test_job_url_is_deduped_against_a_later_search():
    session = _FakeSession({0: ["k1", "k2"]})
    input_model = IndeedScrapeInput(
        startUrls=[
            {"url": "https://www.indeed.com/viewjob?jk=k1"},
            {"url": "https://www.indeed.com/jobs?q=dev"},
        ],
        maxItemsPerQuery=100,
    )
    items = await _collect(input_model, session)
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
    assert items[0]["title"] == "Detailed k1"  # the job page's item, not the card


@pytest.mark.asyncio
async def test_job_url_already_found_by_a_search_is_not_fetched(monkeypatch):
    # One target at a time (the kill switch), the search's keys are known before
    # the job target starts. Concurrent targets may fetch it; see below.
    monkeypatch.setattr(scraper, "_CONCURRENCY", 1)
    session = _FakeSession({0: ["k1", "k2"]})
    input_model = IndeedScrapeInput(
        startUrls=[
            {"url": "https://www.indeed.com/jobs?q=dev"},
            {"url": "https://www.indeed.com/viewjob?jk=k1"},
        ],
        maxItemsPerQuery=100,
    )
    items = await _collect(input_model, session)
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
    assert not any("/viewjob" in u for u in session.fetched)


@pytest.mark.asyncio
async def test_a_failed_job_page_does_not_hide_the_job_from_a_search():
    session = _FakeSession({0: ["k1"]}, details={"k1": "<html>gone</html>"})
    input_model = IndeedScrapeInput(
        startUrls=[
            {"url": "https://www.indeed.com/viewjob?jk=k1"},
            {"url": "https://www.indeed.com/jobs?q=dev"},
        ],
        maxItemsPerQuery=100,
    )
    items = await _collect(input_model, session)
    assert [i["jobKey"] for i in items] == ["k1"]
    assert items[0]["title"] == "Job k1"


@pytest.mark.asyncio
async def test_company_page_items_link_the_company_from_the_slug():
    session = _FakeSession({0: ["k1"]})
    input_model = IndeedScrapeInput(
        startUrls=[{"url": "https://www.indeed.com/cmp/Google/jobs"}]
    )
    [item] = await _collect(input_model, session)
    assert item["companyUrl"] == "https://www.indeed.com/cmp/Google"


class _RichSession:
    """A search card with a clean company link and no pay, and its detail page."""

    def __init__(self, **card_fields: object) -> None:
        card = {
            "jobkey": "k1",
            "displayTitle": "Card title",
            "company": "Acme",
            "companyOverviewLink": "/cmp/Acme",
            "snippet": "short snippet",
            **card_fields,
        }
        model = {"metaData": {"mosaicProviderJobCardsModel": {"results": [card]}}}
        self.search = (
            'window.mosaic.providerData["mosaic-provider-jobcards"]='
            f"{json.dumps(model)};"
        )
        detail = {
            "jobKey": "k1",
            "salaryInfoModel": {
                "salaryMin": 10,
                "salaryMax": 20,
                "salaryCurrency": "USD",
                "salaryType": "HOURLY",
                "salaryText": "$10 - $20 an hour",
            },
            "jobInfoWrapperModel": {
                "jobInfoModel": {
                    "sanitizedJobDescription": "<div>Full description</div>",
                    "jobInfoHeaderModel": {
                        "jobTitle": "Detail title",
                        "companyName": "Acme",
                        "companyOverviewLink": "https://www.indeed.com/cmp/Acme?campaignid=mobvjcmp&tk=t0k",
                        "companyReviewModel": {
                            "ratingsModel": {"rating": 4.0, "count": 10}
                        },
                        "remoteWorkModel": {"type": "HYBRID"},
                    },
                }
            },
        }
        self.detail = (
            "<html><script>window._rootProps = "
            f"{json.dumps({'preloadedVJData': detail})};</script></html>"
        )

    async def fetch_page(self, url: str, *, details_for=None, max_rotations=None):
        wanted = details_for(self.search) if details_for else {}
        model = extract_initial_data(self.detail)
        return Fetched(self.search, dict.fromkeys(wanted, model))


@pytest.mark.asyncio
async def test_details_fill_blank_listing_fields_and_keep_the_rest():
    items = await _collect(
        IndeedScrapeInput(queries=["dev"], scrapeJobDetails=True), _RichSession()
    )
    [item] = items
    assert item["title"] == "Card title"
    assert item["companyUrl"] == "https://www.indeed.com/cmp/Acme"
    assert item["companyRating"] == 4.0
    assert item["companyReviewCount"] == 10
    # The card said not remote; the job page's work model says hybrid.
    assert (item["isRemote"], item["remoteType"]) == (True, "HYBRID")
    assert item["salary"]["salaryText"] == "$10 - $20 an hour"
    assert (item["salary"]["salaryMin"], item["salary"]["period"]) == (10, "hour")
    # The description is the reason to fetch details, so it always wins.
    assert item["descriptionText"] == "Full description"
    assert item["descriptionHtml"] == "<div>Full description</div>"


@pytest.mark.asyncio
async def test_a_card_salary_with_text_alone_gets_the_detail_s_bounds():
    # Live: 'From $20 an hour' cards carry no extractedSalary; the whole-dict
    # fill saw the text and kept the bounds and period null.
    session = _RichSession(salarySnippet={"text": "From $10 an hour"})
    [item] = await _collect(
        IndeedScrapeInput(queries=["dev"], scrapeJobDetails=True), session
    )
    salary = item["salary"]
    assert salary["salaryText"] == "From $10 an hour"  # the card's own words
    assert (salary["salaryMin"], salary["salaryMax"]) == (10, 20)
    assert (salary["currency"], salary["period"]) == ("USD", "hour")


class _SlowSession(_FakeSession):
    """Search pages that take ``delays[query]`` seconds, recording overlap."""

    def __init__(self, keys: dict[str, list[str]], delays: dict[str, float]) -> None:
        super().__init__({})
        self._keys = keys
        self._delays = delays
        self.in_flight = 0
        self.peak = 0
        self.started: list[str] = []

    async def fetch_page(self, url: str, *, details_for=None, max_rotations=None):
        query = parse_qs(urlparse(url).query)["q"][0]
        self.started.append(query)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        try:
            await asyncio.sleep(self._delays.get(query, 0))
        finally:
            self.in_flight -= 1
        return Fetched(_page_html(self._keys[query]))


@pytest.mark.asyncio
async def test_targets_run_concurrently_but_merge_in_input_order():
    # The first query is the slowest; its items still come first, and the
    # duplicate k2 from the faster second query is dropped.
    session = _SlowSession(
        {"a": ["k1", "k2"], "b": ["k2", "k3"], "c": ["k4"]},
        {"a": 0.2, "b": 0.0, "c": 0.05},
    )
    # Three pages of 25 cannot fill 100 items, so all three start at once.
    items = await _collect(
        IndeedScrapeInput(queries=["a", "b", "c"], maxItems=100, maxItemsPerQuery=25),
        session,
    )
    assert [i["jobKey"] for i in items] == ["k1", "k2", "k3", "k4"]
    assert session.peak == 3


@pytest.mark.asyncio
async def test_concurrency_is_bounded_and_the_limit_stops_later_targets(monkeypatch):
    monkeypatch.setattr(scraper, "_CONCURRENCY", 2)
    queries = [f"q{i}" for i in range(6)]
    session = _SlowSession(
        {q: [f"{q}-1", f"{q}-2"] for q in queries}, dict.fromkeys(queries, 0.02)
    )
    items = await scrape_indeed(
        IndeedScrapeInput(queries=queries, maxItems=3, maxItemsPerQuery=2),
        limit=3,
        session=session,
    )
    assert [i["jobKey"] for i in items] == ["q0-1", "q0-2", "q1-1"]
    assert session.peak == 2
    # Two pages of two fill three items: nothing past them was started.
    assert session.started == ["q0", "q1"]


@pytest.mark.asyncio
async def test_a_page_that_can_fill_the_limit_runs_alone():
    # Live (review, defaults 25/25, two queries): both pages loaded and sent 24
    # spa=1 requests each, and every item came from the first.
    queries = ["q0", "q1", "q2"]
    session = _SlowSession({q: [f"{q}-{i}" for i in range(30)] for q in queries}, {})
    items = await scrape_indeed(
        IndeedScrapeInput(queries=queries, maxItems=25, maxItemsPerQuery=25),
        limit=25,
        session=session,
    )
    assert len(items) == 25
    assert session.started == ["q0"]


@pytest.mark.asyncio
async def test_a_short_page_lets_the_next_target_start():
    queries = ["q0", "q1", "q2"]
    keys = {"q0": ["q0-0", "q0-1"], "q1": [f"q1-{i}" for i in range(30)], "q2": []}
    session = _SlowSession(keys, {})
    items = await scrape_indeed(
        IndeedScrapeInput(queries=queries, maxItems=25, maxItemsPerQuery=25),
        limit=25,
        session=session,
    )
    assert [i["jobKey"] for i in items][:3] == ["q0-0", "q0-1", "q1-0"]
    assert len(items) == 25
    # q0 gave 2, so q1 was needed; q0 and q1 could then give 27, so q2 was not.
    assert session.started == ["q0", "q1"]


@pytest.mark.asyncio
async def test_concurrent_job_url_found_by_a_search_is_emitted_once():
    session = _FakeSession({0: ["k1", "k2"]})
    input_model = IndeedScrapeInput(
        startUrls=[
            {"url": "https://www.indeed.com/jobs?q=dev"},
            {"url": "https://www.indeed.com/viewjob?jk=k1"},
        ],
        maxItemsPerQuery=100,
    )
    items = await _collect(input_model, session)
    assert [i["jobKey"] for i in items] == ["k1", "k2"]
    assert items[0]["title"] == "Job k1"  # the search card came first


@pytest.mark.asyncio
async def test_details_use_the_inline_answer_for_the_first_job():
    cards = [
        {"jobkey": k, "displayTitle": k, "viewJobLink": f"/viewjob?jk={k}&from=vjs"}
        for k in ("k1", "k2")
    ]
    model = {"metaData": {"mosaicProviderJobCardsModel": {"results": cards}}}

    def viewjob(jk: str, text: str) -> dict:
        info = {"jobInfoModel": {"sanitizedJobDescription": f"<p>{text}</p>"}}
        return {"jobKey": jk, "jobInfoWrapperModel": info}

    inline = {"status": "success", "body": viewjob("k1", "Inline k1")}
    html = (
        f'<script>{{"autoOpenTwoPaneViewjobResponse":{json.dumps(inline)}}}</script>'
        f'window.mosaic.providerData["mosaic-provider-jobcards"]={json.dumps(model)};'
    )
    asked: list[dict] = []

    class _Session:
        async def fetch_page(self, url, *, details_for=None, max_rotations=None):
            asked.append(details_for(html))
            return Fetched(html, {"k2": viewjob("k2", "Spa k2")})

    items = await _collect(
        IndeedScrapeInput(queries=["dev"], scrapeJobDetails=True), _Session()
    )
    # Only k2 is asked for, through Indeed's own pane link.
    assert asked == [{"k2": "/viewjob?jk=k2&from=vjs&spa=1"}]
    assert [i["descriptionText"] for i in items] == ["Inline k1", "Spa k2"]
