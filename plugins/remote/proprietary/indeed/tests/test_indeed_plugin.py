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
from proprietary.indeed import scraper
from proprietary.indeed.fetch import IndeedAccessBlockedError
from proprietary.license_check import keygen
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT, StandInKeygen

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def indeed(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Indeed plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setattr(keygen, "KEYGEN_API_URL", keygen_url)
        monkeypatch.setattr(keygen, "SURFSENSE_ACCOUNT_ID", ACCOUNT)
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

    async def fetch_html(self, url: str, *, max_rotations: int | None = None) -> str:
        self.fetched.append(url)
        return self.answer(url)


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
    summary = result.content[0].text
    assert "Engineer k1, Acme, Remote https://uk.indeed.com/viewjob?jk=k1" in summary
    assert progress == [1, 2]


async def test_a_url_is_scraped_as_it_is(indeed: str, jobs: Pages) -> None:
    result = await call(
        indeed,
        "scrape",
        {"urls": ["https://www.indeed.com/cmp/Acme/jobs"]},
        LICENSE,
    )

    assert not result.is_error
    assert jobs.fetched == ["https://www.indeed.com/cmp/Acme/jobs"]


async def test_a_block_reads_as_the_tool_s_error(indeed: str, blocked: Pages) -> None:
    """Not as no jobs: the agent may try again later."""
    result = await call(indeed, "scrape", {"search_queries": ["dev"]}, LICENSE)

    assert result.is_error
    assert "Indeed refused anonymous access" in result.content[0].text


async def test_a_call_naming_nothing_to_scrape_is_refused(
    indeed: str, jobs: Pages
) -> None:
    result = await call(indeed, "scrape", {}, LICENSE)

    assert result.is_error
    assert "at least one of" in result.content[0].text
    assert jobs.fetched == []


async def test_a_url_that_is_not_http_is_refused(indeed: str, jobs: Pages) -> None:
    result = await call(indeed, "scrape", {"urls": ["file:///etc/passwd"]}, LICENSE)

    assert result.is_error
    assert "file:///etc/passwd" in result.content[0].text
    assert jobs.fetched == []


def test_without_a_license_the_plugin_answers_nothing(indeed: str) -> None:
    refused = httpx2.post(indeed, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
