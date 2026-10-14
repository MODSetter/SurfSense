"""The Instagram plugin as the app reaches it: its MCP server on the host, behind the license.

Instagram is faked at the scraper's network seam, `fetch_json` and `fetch_html`,
and its proxy sessions; the host, the license check, the tools and the parsing are real.
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
from proprietary.instagram import scraper
from proprietary.instagram.fetch import InstagramAccessBlockedError
from proprietary.license_check.tests.stand_in_keygen import (
    ACCOUNT,
    StandInKeygen,
    accounts_url,
)

LICENSE = {"Authorization": "License k-1"}


@pytest.fixture
def instagram(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Instagram plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"instagram"})) as base:
            yield f"{base}/instagram/mcp"


def media(number: int) -> dict[str, Any]:
    """One post as a profile's `web_profile_info` lists it."""
    return {
        "node": {
            "__typename": "GraphImage",
            "id": f"m{number}",
            "shortcode": f"C{number}",
            "edge_media_to_caption": {
                "edges": [{"node": {"text": f"Sunset {number}"}}]
            },
            "owner": {"id": "7", "username": "natgeo"},
            "taken_at_timestamp": 1_790_000_000 + number,
        }
    }


def profile(username: str) -> dict[str, Any]:
    """`web_profile_info` for a profile with three posts."""
    return {
        "data": {
            "user": {
                "id": "7",
                "username": username,
                "full_name": "National Geographic",
                "edge_followed_by": {"count": 280_000_000},
                "edge_owner_to_timeline_media": {
                    "count": 3,
                    "edges": [media(n) for n in (1, 2, 3)],
                },
            }
        }
    }


@pytest.fixture
def instagram_answers(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict]]:
    """Instagram answering every profile; keeps each path asked for."""
    asked: list[tuple[str, dict]] = []

    async def fetch_json(path: str, params: dict | None = None) -> Any:
        asked.append((path, params or {}))
        return profile((params or {})["username"])

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_json", fetch_json)
    return asked


@pytest.fixture
def walled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Instagram's login wall on every address."""

    async def refused(path: str, params: dict | None = None) -> Any:
        raise InstagramAccessBlockedError("login wall on every address")

    no_proxy_sessions(monkeypatch)
    monkeypatch.setattr(scraper, "fetch_json", refused)
    monkeypatch.setattr(scraper, "fetch_html", refused)


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
    instagram: str, instagram_answers: list[tuple[str, dict]]
) -> None:
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
    assert progress == [1, 2]
    assert instagram_answers[0][1] == {"username": "natgeo"}


async def test_a_profile_s_details_come_with_a_summary_and_progress(
    instagram: str, instagram_answers: list[tuple[str, dict]]
) -> None:
    progress: list[float] = []

    result = await call(
        instagram, "details", {"search_queries": ["@natgeo"]}, LICENSE, progress
    )

    assert not result.is_error
    (item,) = result.structured_content["items"]
    assert (item["username"], item["followersCount"]) == ("natgeo", 280_000_000)
    summary = result.content[0].text
    assert summary.startswith("1 Instagram profile")
    assert "@natgeo" in summary
    assert "https://www.instagram.com/natgeo/" in summary
    assert progress == [1]


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
