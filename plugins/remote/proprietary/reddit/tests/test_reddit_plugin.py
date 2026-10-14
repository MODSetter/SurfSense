"""The Reddit plugin as the app reaches it: its MCP server on the host, behind the license.

Reddit itself is faked at the scraper's network seam, `fetch_json`, and its proxy
sessions; the host, the license check, the tool and Reddit's parsing are real.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)
from proprietary.reddit import scraper
from proprietary.reddit.fetch import RedditAccessBlockedError

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def reddit(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Reddit plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"reddit"})) as base:
            yield f"{base}/reddit/mcp"


def post(number: int) -> dict[str, Any]:
    """One search result as Reddit's `.json` lists it."""
    return {
        "kind": "t3",
        "data": {
            "name": f"t3_p{number}",
            "id": f"p{number}",
            "title": f"Post {number}",
            "author": "ada",
            "subreddit": "python",
            "subreddit_name_prefixed": "r/python",
            "permalink": f"/r/python/comments/p{number}/post/",
            "score": 10 * number,
            "num_comments": number,
            "created_utc": 1_790_000_000 + number,
        },
    }


@pytest.fixture
def reddit_answers(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """Reddit answering a search with three posts; keeps each path asked for."""
    asked: list[tuple[str, dict]] = []

    async def fetch_json(path: str, params: dict | None = None) -> Any:
        asked.append((path, params or {}))
        return {"data": {"children": [post(n) for n in (1, 2, 3)], "after": None}}

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_json", fetch_json)
    return asked


def no_proxy_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    class Holder:
        async def close(self) -> None:
            pass

    async def open_holder() -> Holder:
        return Holder()

    @asynccontextmanager
    async def bind(holder: Holder) -> AsyncIterator[Holder]:
        yield holder

    monkeypatch.setattr(scraper, "open_proxy_holder", open_holder)
    monkeypatch.setattr(scraper, "bind_proxy_holder", bind)


async def test_it_offers_one_read_only_tool_that_reaches_the_web(reddit: str) -> None:
    """Read-only and open-world, so the app lets a first-party read skip asking."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(reddit, http_client=http)) as client,
    ):
        (tool,) = (await client.list_tools()).tools

    assert tool.name == "scrape"
    assert tool.annotations is not None
    assert (tool.annotations.read_only_hint, tool.annotations.open_world_hint) == (
        True,
        True,
    )


async def test_a_search_returns_its_posts_with_a_summary_and_progress(
    reddit: str, reddit_answers: list[tuple[str, dict]]
) -> None:
    progress: list[float] = []

    result = await call(
        reddit,
        "scrape",
        {"search_queries": ["asyncio"], "max_items": 2, "skip_comments": True},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["title"] for item in items] == ["Post 1", "Post 2"]
    assert result.content[0].text.startswith("2 Reddit items")
    assert progress[-1] == 2
    assert reddit_answers[0][0] == "search"
    assert reddit_answers[0][1]["q"] == "asyncio"


async def test_reddit_refusing_every_address_reads_as_the_tool_s_error(
    reddit: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Said as Reddit's refusal, so the agent stops rather than retrying."""

    async def refused(path: str, params: dict | None = None) -> Any:
        raise RedditAccessBlockedError("every address was refused")

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_json", refused)

    result = await call(reddit, "scrape", {"search_queries": ["asyncio"]}, LICENSE)

    assert result.is_error
    assert "Reddit refused" in result.content[0].text


async def test_a_call_naming_nothing_to_scrape_is_refused(reddit: str) -> None:
    result = await call(reddit, "scrape", {}, LICENSE)

    assert result.is_error
    assert "urls" in result.content[0].text


def test_without_a_license_the_plugin_answers_nothing(reddit: str) -> None:
    refused = httpx2.post(reddit, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
