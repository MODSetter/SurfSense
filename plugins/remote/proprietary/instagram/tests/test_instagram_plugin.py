"""The Instagram plugin as the app reaches it: its MCP server on the host, behind the license.

Instagram is faked at the scraper's network seam, `fetch_html`,
and its proxy sessions; the host, the license check, the tools and the parsing are real.
"""

import importlib
import json
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.tests.mcp_calls import call
from mcp_server import progress as progress_module
from proprietary.instagram import scraper
from proprietary.instagram.fetch import (
    InstagramAccessBlockedError,
    InstagramLoginRequiredError,
)
from proprietary.instagram.tests.on_the_host import LICENSE, no_proxy_sessions
from proprietary.instagram.tests.profile_pages import profile_pages
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT


@pytest.fixture
def instagram_answers(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Instagram serving every profile's page and embed, three posts; keeps each path."""
    asked: list[str] = []

    async def fetch_html(path: str, params: dict | None = None) -> str | None:
        asked.append(path)
        return profile_pages(path.split("/", 1)[0], [1, 2, 3]).get(path)

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_html", fetch_html)
    return asked


@pytest.fixture
def walled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Instagram's login wall on every address."""

    async def refused(path: str, params: dict | None = None) -> Any:
        raise InstagramAccessBlockedError("login wall on every address")

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_html", refused)


async def test_it_offers_two_read_only_tools_that_reach_the_web(
    instagram: str,
) -> None:
    """Read-only and open-world, so the app lets a first-party read skip asking."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(instagram, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert sorted(tool.name for tool in tools) == ["details", "scrape"]
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.read_only_hint is True
        assert tool.annotations.open_world_hint is True


async def test_a_profile_s_posts_come_with_a_summary_and_progress(
    instagram: str,
    instagram_answers: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Unthrottled, so every stage shows: the opening stage (0.5), then each item.
    monkeypatch.setattr(progress_module, "INTERVAL_SECONDS", 0.0)
    progress: list[float] = []

    result = await call(
        instagram,
        "scrape",
        {"urls": ["https://www.instagram.com/natgeo/"], "max_items": 2},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["caption"] for item in items] == ["Sunset 1", "Sunset 2"]
    summary = result.content[0].text
    assert summary.startswith("2 Instagram posts")
    assert "Sunset 1" in summary
    assert "https://www.instagram.com/p/C1/" in summary
    assert progress == [0.5, 1, 2]
    assert instagram_answers[0] == "natgeo/"


async def test_a_profile_s_details_come_with_a_summary_and_progress(
    instagram: str,
    instagram_answers: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(progress_module, "INTERVAL_SECONDS", 0.0)
    progress: list[float] = []

    result = await call(
        instagram, "details", {"search_queries": ["@natgeo"]}, LICENSE, progress
    )

    assert not result.is_error
    (item,) = result.structured_content["items"]
    assert (item["username"], item["followersCount"]) == ("natgeo", 280_000_000)
    summary = result.content[0].text
    assert summary.startswith("1 Instagram profile")
    # Each profile is its own JSON line now, not an "@handle" bullet.
    assert '"username":"natgeo"' in summary
    assert "https://www.instagram.com/natgeo/" in summary
    assert progress == [0.5, 1]


async def test_each_post_is_a_line_of_the_fields_an_agent_needs(
    instagram: str, instagram_answers: list[str]
) -> None:
    """opencode reads only the text, so the posts go there, without ids or media URLs."""
    result = await call(
        instagram,
        "scrape",
        {"urls": ["https://www.instagram.com/natgeo/"], "max_items": 2},
        LICENSE,
    )

    header, first, second = result.content[0].text.splitlines()
    assert header == "2 Instagram posts"
    post = json.loads(first)
    assert post["caption"] == "Sunset 1"
    assert post["url"] == "https://www.instagram.com/p/C1/"
    assert post["ownerUsername"] == "natgeo"
    assert post["timestamp"]
    assert not {"id", "shortCode", "ownerId", "scrapedAt", "inputUrl"} & post.keys()
    assert json.loads(second)["caption"] == "Sunset 2"
    # The whole item stays in the structured result.
    assert result.structured_content["items"][0]["shortCode"] == "C1"


async def test_a_profile_line_carries_its_counts_and_latest_posts(
    instagram: str, instagram_answers: list[str]
) -> None:
    result = await call(
        instagram,
        "details",
        {"urls": ["natgeo"]},
        {**LICENSE, "x-surfsense-text-only": "1"},
    )

    assert result.structured_content is None
    header, line = result.content[0].text.splitlines()
    assert header == "1 Instagram profiles"
    profile_line = json.loads(line)
    assert profile_line["username"] == "natgeo"
    assert profile_line["fullName"] == "National Geographic"
    assert profile_line["followersCount"] == 280_000_000
    assert [post["caption"] for post in profile_line["latestPosts"]] == [
        "Sunset 1",
        "Sunset 2",
        "Sunset 3",
    ]
    assert "id" not in profile_line
    assert "id" not in profile_line["latestPosts"][0]


def test_an_error_item_reads_as_its_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # server.py checks for Keygen's account at import, as the host loads it.
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
    server = importlib.import_module("proprietary.instagram.server")
    item = {
        "inputUrl": "https://www.instagram.com/p/X/",
        "error": "not_found",
        "errorDescription": "No such post",
        "caption": None,
        "url": None,
    }

    assert server._projected_post(item) == {
        "inputUrl": "https://www.instagram.com/p/X/",
        "error": "not_found",
        "errorDescription": "No such post",
    }
    assert server._summary([item, {"error": None}], "posts") == (
        "2 Instagram posts, 1 errors"
    )


async def test_a_login_wall_on_every_address_reads_as_the_tool_s_error(
    instagram: str, walled: None
) -> None:
    """Said as Instagram's refusal, so the agent stops rather than retrying."""
    scraped = await call(instagram, "scrape", {"urls": ["natgeo"]}, LICENSE)
    detailed = await call(instagram, "details", {"urls": ["natgeo"]}, LICENSE)

    assert scraped.is_error
    assert "Instagram requires a login" in scraped.content[0].text
    assert detailed.is_error
    assert "Instagram refused anonymous access" in detailed.content[0].text


async def test_the_profile_login_wall_names_what_still_works(
    instagram: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not 'provide a profile URL': the caller gave one, and it cannot work."""

    async def walled(path: str, params: dict | None = None) -> Any:
        raise InstagramLoginRequiredError("Instagram requires a login for natgeo")

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_html", walled)

    scraped = await call(instagram, "scrape", {"urls": ["natgeo"]}, LICENSE)
    detailed = await call(instagram, "details", {"urls": ["natgeo"]}, LICENSE)

    for result in (scraped, detailed):
        assert result.is_error
        text = result.content[0].text
        assert "requires a login for natgeo" in text
        assert "Single post and reel URLs" in text
        assert "instagram.com/p/<code>/" in text
        assert "Provide a profile URL" not in text


async def test_scrape_no_longer_offers_the_unimplemented_add_parent_data(
    instagram: str,
) -> None:
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(instagram, http_client=http)) as client,
    ):
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    assert "add_parent_data" not in tools["scrape"].input_schema["properties"]


@pytest.mark.parametrize("tool", ["scrape", "details"])
async def test_a_call_naming_nothing_is_refused(instagram: str, tool: str) -> None:
    result = await call(instagram, tool, {}, LICENSE)

    assert result.is_error
    assert "urls" in result.content[0].text


@pytest.mark.parametrize("tool", ["scrape", "details"])
async def test_urls_and_searches_together_are_refused(
    instagram: str, tool: str
) -> None:
    result = await call(
        instagram, tool, {"urls": ["natgeo"], "search_queries": ["nasa"]}, LICENSE
    )

    assert result.is_error
    assert "not both" in result.content[0].text


def test_without_a_license_the_plugin_answers_nothing(instagram: str) -> None:
    refused = httpx2.post(instagram, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})


async def test_scrape_says_where_a_video_s_url_comes_from(instagram: str) -> None:
    """A feed's newest posts come without one; a post URL reads the post's own page."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(instagram, http_client=http)) as client,
    ):
        tools = {tool.name: tool for tool in (await client.list_tools()).tools}

    description = tools["scrape"].description or ""
    assert "video URL" in description
    assert "instagram.com/p/<code>/" in description
