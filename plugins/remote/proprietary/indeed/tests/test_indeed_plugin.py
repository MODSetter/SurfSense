"""The Indeed plugin as the app reaches it: its MCP server on the host, behind the license.

Indeed is faked at the scraper's session seam, `open_session`, so no browser starts;
the host, the license check, the tool and Indeed's parsing are real.
"""

import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from mcp_server.results import tool_result
from proprietary.indeed import scraper
from proprietary.indeed.fetch import Fetched, IndeedAccessBlockedError
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def indeed(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Indeed plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"indeed"})) as base:
            yield f"{base}/indeed/mcp"


def search_page(keys: list[str]) -> str:
    """A search page carrying its job cards as Indeed embeds them."""
    results = [
        {
            "jobkey": key,
            "displayTitle": f"Engineer {key}",
            "company": "Acme",
            "formattedLocation": "Remote",
            "salarySnippet": {"text": "$90,000 a year", "currency": "USD"},
            "extractedSalary": {"min": 90000, "max": 90000, "type": "YEARLY"},
        }
        for key in keys
    ]
    model = {"metaData": {"mosaicProviderJobCardsModel": {"results": results}}}
    return (
        f'window.mosaic.providerData["mosaic-provider-jobcards"]={json.dumps(model)};'
    )


class Pages:
    """Indeed answering each page with `answer(url)`; keeps each URL fetched."""

    def __init__(self, answer) -> None:
        self.answer = answer
        self.fetched: list[str] = []

    async def fetch_page(self, url: str, *, details_for=None, max_rotations=None):
        self.fetched.append(url)
        return Fetched(self.answer(url))


def fake_indeed(monkeypatch: pytest.MonkeyPatch, answer) -> Pages:
    pages = Pages(answer)

    @asynccontextmanager
    async def open_session() -> AsyncIterator[Pages]:
        yield pages

    monkeypatch.setattr(scraper, "open_session", open_session)
    return pages


@pytest.fixture
def jobs(monkeypatch: pytest.MonkeyPatch) -> Pages:
    """Indeed answering every search with three jobs."""
    return fake_indeed(monkeypatch, lambda url: search_page(["k1", "k2", "k3"]))


@pytest.fixture
def blocked(monkeypatch: pytest.MonkeyPatch) -> Pages:
    """Indeed walling every address the session tried."""

    def refuse(url: str) -> str:
        raise IndeedAccessBlockedError(f"Indeed refused {url} after 4 attempt(s)")

    return fake_indeed(monkeypatch, refuse)


@pytest.mark.asyncio
async def test_it_offers_one_read_only_tool_that_reaches_the_web(indeed: str) -> None:
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(indeed, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert [tool.name for tool in tools] == ["scrape"]
    assert tools[0].annotations is not None
    assert tools[0].annotations.read_only_hint is True
    assert tools[0].annotations.open_world_hint is True


@pytest.mark.asyncio
async def test_a_search_returns_its_jobs_with_a_summary_and_progress(
    indeed: str, jobs: Pages
) -> None:
    progress: list[float] = []

    result = await call(
        indeed,
        "scrape",
        {
            "search_queries": ["data analyst"],
            "country": "gb",
            "location": "London",
            "job_type": "fulltime",
            "max_items": 2,
        },
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["jobKey"] for item in items] == ["k1", "k2"]
    assert jobs.fetched[0].startswith("https://uk.indeed.com/jobs?q=data+analyst")
    assert "l=London" in jobs.fetched[0] and "jt=fulltime" in jobs.fetched[0]
    # The agent reads each job as a line of JSON after the header; opencode keeps
    # only the text, so the pay and the link must be in it.
    header, *lines = result.content[0].text.splitlines()
    assert header == "2 Indeed jobs"
    first = json.loads(lines[0])
    assert first["title"] == "Engineer k1"
    assert (first["company"], first["location"]) == ("Acme", "Remote")
    assert first["salary"] == "$90,000 a year"
    assert (first["salaryMin"], first["period"]) == (90000, "year")
    assert first["jobUrl"] == "https://uk.indeed.com/viewjob?jk=k1"
    assert "scrapedAt" not in first and "applyUrl" not in first
    # Stages are rate-limited to one a second, but the first and the one that
    # reaches the total always arrive, and the value only rises.
    assert progress[0] < 1 and progress[-1] == 2
    assert progress == sorted(progress)


@pytest.mark.asyncio
async def test_a_url_is_scraped_as_it_is(indeed: str, jobs: Pages) -> None:
    result = await call(
        indeed,
        "scrape",
        {"urls": ["https://www.indeed.com/cmp/Acme/jobs"]},
        LICENSE,
    )

    assert not result.is_error
    assert jobs.fetched == ["https://www.indeed.com/cmp/Acme/jobs"]


@pytest.mark.asyncio
async def test_a_block_reads_as_the_tool_s_error(indeed: str, blocked: Pages) -> None:
    """Not as no jobs: the agent may try again later."""
    result = await call(indeed, "scrape", {"search_queries": ["dev"]}, LICENSE)

    assert result.is_error
    assert "Indeed refused anonymous access" in result.content[0].text


@pytest.mark.asyncio
async def test_a_call_naming_nothing_to_scrape_is_refused(
    indeed: str, jobs: Pages
) -> None:
    result = await call(indeed, "scrape", {}, LICENSE)

    assert result.is_error
    assert "at least one of" in result.content[0].text
    assert jobs.fetched == []


@pytest.mark.asyncio
async def test_a_url_that_is_not_http_is_refused(indeed: str, jobs: Pages) -> None:
    result = await call(indeed, "scrape", {"urls": ["file:///etc/passwd"]}, LICENSE)

    assert result.is_error
    assert "file:///etc/passwd" in result.content[0].text
    assert jobs.fetched == []


def test_without_a_license_the_plugin_answers_nothing(indeed: str) -> None:
    refused = httpx2.post(indeed, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})


def test_twenty_five_detailed_jobs_all_fit_in_the_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The server module checks licenses from import on.
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
    from proprietary.indeed.server import _projected, _summary

    # Live (registered nurse, details on): 2,000-character descriptions filled
    # the text after 13 jobs, so a text-only client never saw the other 12.
    description = "• Provide patient care and document it in the record. " * 60
    items = [
        {
            "title": f"Registered Nurse - Medical Surgical Unit {i}",
            "company": "Northwestern Memorial HealthCare",
            "formattedLocation": "Chicago, IL 60611",
            "salary": {
                "salaryText": "$38.50 - $62.00 an hour",
                "salaryMin": 38.5,
                "salaryMax": 62.0,
                "currency": "USD",
                "period": "hour",
            },
            "jobTypes": ["Full-time"],
            "benefits": ["Health insurance", "Paid time off", "401(k)"],
            "companyRating": 4.1,
            "companyReviewCount": 2345,
            "age": "Posted 3 days ago",
            "jobUrl": f"https://www.indeed.com/viewjob?jk={i:016x}",
            "companyUrl": "https://www.indeed.com/cmp/Northwestern-Memorial-Healthcare",
            "descriptionText": description,
            "descriptionHtml": f"<p>{description}</p>",
        }
        for i in range(25)
    ]
    text = tool_result(_summary(items), items, project=_projected).content[0].text
    header, *lines = text.splitlines()
    assert header == "25 Indeed jobs, 25 with full descriptions"
    assert len(lines) == 25
    assert json.loads(lines[-1])["description"].endswith("…")
