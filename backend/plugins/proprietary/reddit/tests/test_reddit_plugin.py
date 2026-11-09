"""The Reddit plugin as the app reaches it: its MCP server on the host, behind the license.

Reddit itself is faked at the scraper's read seam, `read_listing`, and its proxy
sessions; the host, the license check, the tool and Reddit's parsing are real.
"""

import json
import time
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.tests.mcp_calls import call
from mcp_server import progress as progress_module
from proprietary.reddit import fetch, scraper
from proprietary.reddit.fetch import RedditAccessBlockedError
from proprietary.reddit.tests.on_the_host import LICENSE, no_proxy_sessions


def post(number: int) -> dict[str, Any]:
    """One search result in the listing shape the scraper reads."""
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

    async def read_listing(path: str, params: dict | None = None) -> Any:
        asked.append((path, params or {}))
        return {"data": {"children": [post(n) for n in (1, 2, 3)], "after": None}}

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "read_listing", read_listing)
    return asked


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


async def test_each_item_is_a_line_of_its_fields_an_agent_needs(
    reddit: str, reddit_answers: list[tuple[str, dict]]
) -> None:
    """opencode reads only the text, so the items go there, without ids or HTML."""
    result = await call(
        reddit,
        "scrape",
        {"search_queries": ["asyncio"], "max_items": 2, "skip_comments": True},
        LICENSE,
    )

    header, *lines = result.content[0].text.splitlines()
    assert header == "2 Reddit items: 2 posts"
    first = json.loads(lines[0])
    assert first == {
        "dataType": "post",
        "title": "Post 1",
        "communityName": "r/python",
        "username": "ada",
        "url": "https://www.reddit.com/r/python/comments/p1/post/",
        "upVotes": 10,
        "numberOfComments": 1,
        "createdAt": first["createdAt"],
    }
    # The whole item, ids included, stays in the structured result.
    assert result.structured_content["items"][0]["id"] == "t3_p1"


async def test_a_text_only_client_gets_no_structured_copy(
    reddit: str, reddit_answers: list[tuple[str, dict]]
) -> None:
    result = await call(
        reddit,
        "scrape",
        {"search_queries": ["asyncio"], "max_items": 1, "skip_comments": True},
        {**LICENSE, "x-surfsense-text-only": "1"},
    )

    assert not result.is_error
    assert result.structured_content is None
    assert '"title":"Post 1"' in result.content[0].text


async def test_warms_and_fetches_reach_the_client_as_progress(
    reddit: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A call spent warming browsers says so, instead of a silent stream."""
    monkeypatch.setattr(progress_module, "INTERVAL_SECONDS", 0.0)

    async def read_listing(path: str, params: dict | None = None) -> Any:
        # What fetch.py reports from inside the fan-out's own tasks.
        await fetch._stage("warming an anonymous session (us)")
        await fetch._stage(f"fetching {path}")
        return {"data": {"children": [post(1)], "after": None}}

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "read_listing", read_listing)
    heard: list[tuple[float, str | None]] = []

    async def on_progress(value: float, total: float | None, message: str | None):
        heard.append((value, message))

    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(reddit, http_client=http)) as client,
    ):
        result = await client.call_tool(
            "scrape",
            {"search_queries": ["asyncio"], "max_items": 1, "skip_comments": True},
            progress_callback=on_progress,
        )

    assert not result.is_error
    messages = [message for _, message in heard]
    assert messages == [
        "scraping Reddit",
        "warming an anonymous session (us)",
        "fetching search",
        "1 of 1 items",
    ]
    values = [value for value, _ in heard]
    assert values == sorted(values) and values[-1] == 1


async def test_reddit_refusing_every_address_reads_as_the_tool_s_error(
    reddit: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Said as Reddit's refusal, so the agent stops rather than retrying."""

    async def refused(path: str, params: dict | None = None) -> Any:
        raise RedditAccessBlockedError("every address was refused")

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "read_listing", refused)

    result = await call(reddit, "scrape", {"search_queries": ["asyncio"]}, LICENSE)

    assert result.is_error
    assert "Reddit refused" in result.content[0].text


async def test_while_reddit_is_known_closed_the_call_fails_at_once(
    reddit: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The latch answers before any proxy session or browser warm."""

    async def no_holder() -> Any:
        raise AssertionError("opened a proxy session while latched")

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(fetch, "open_proxy_holder", no_holder)
    fetch._closed.sightings = {"gb": time.monotonic(), "us": time.monotonic()}
    fetch._closed.until = time.monotonic() + 600

    started = time.perf_counter()
    listing = await call(reddit, "scrape", {"community": "python"}, LICENSE)
    searched = await call(reddit, "scrape", {"search_queries": ["fastapi"]}, LICENSE)

    assert time.perf_counter() - started < 5
    for result in (listing, searched):
        assert result.is_error
        text = result.content[0].text
        assert "Reddit refused anonymous access: logged-out reads are closed" in text
        assert "retrying now fails the same way" in text


async def test_a_call_naming_nothing_to_scrape_is_refused(reddit: str) -> None:
    result = await call(reddit, "scrape", {}, LICENSE)

    assert result.is_error
    assert "urls" in result.content[0].text


def test_without_a_license_the_plugin_answers_nothing(reddit: str) -> None:
    refused = httpx2.post(reddit, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
