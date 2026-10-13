"""The Google Maps plugin as the app reaches it: its MCP server on the host, behind the license.

Google is faked at the scraper's network seam, scrapling's `AsyncFetcher.get`, and the
browser tier is switched off; the host, the license check, the tools and Maps' parsing
are real.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest
from mcp.client.client import Client
from mcp.client.streamable_http import streamable_http_client

from host.app import host_app
from host.tests.mcp_calls import call
from host.tests.serving import serving
from proprietary.google_maps import fetch
from proprietary.license_check import keygen
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT, StandInKeygen

LICENSE = {"Authorization": "License k-1"}
FID = "0x89c3ca9c11f90c25:0x6cc8dba851799f09"


@pytest.fixture
def maps(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Google Maps plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setattr(keygen, "KEYGEN_API_URL", keygen_url)
        monkeypatch.setattr(keygen, "SURFSENSE_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"google-maps"})) as base:
            yield f"{base}/google-maps/mcp"


def place(number: int) -> list[Any]:
    """One place `darray` at the positions Maps puts its fields."""
    darray: list[Any] = [None] * 184
    darray[4] = [None] * 9
    darray[4][7], darray[4][8] = 4.5, 100 + number
    darray[10] = f"0x{number:x}:0x{number + 100:x}"
    darray[11] = f"Cafe {number}"
    darray[13] = ["Coffee shop"]
    darray[18] = f"{number} Main St"
    darray[78] = f"ChIJplace{number}"
    return darray


def review(number: int) -> list[Any]:
    """One review as Google's review feed lists it."""
    raw: list[Any] = [None] * 45
    raw[1] = 5
    raw[2] = ["a week ago", None, "1790000000000"]
    raw[3] = ["Ada", None, "https://www.google.com/maps/contrib/42", 3, 0, [None, 1]]
    raw[5] = f"r{number}"
    raw[27] = f"Good coffee {number}"
    return raw


@dataclass
class Page:
    """What scrapling hands back for one GET."""

    html_content: str
    status: int = 200
    cookies: dict[str, str] = field(default_factory=dict)


def rpc(body: Any) -> Page:
    return Page(")]}'\n" + json.dumps(body))


@dataclass
class Google:
    """Google answering Maps' search, place and review requests; keeps each URL asked for."""

    place_page: str = f"<html>window.APP_INITIALIZATION_STATE=[{FID}]</html>"
    asked: list[str] = field(default_factory=list)

    async def get(self, url: str, **_: Any) -> Page:
        self.asked.append(url)
        if "tbm=map" in url and "pb=" in url:
            first_page = "!8i0!" in url
            entries = [[None, 0], *([None] * 14 + [place(n)] for n in (1, 2, 3))]
            return rpc([[None, entries if first_page else []]])
        if "/maps/preview/place" in url:
            return rpc([None] * 6 + [place(7)])
        if "GetLocalBoqProxy" in url:
            node = [None, None, [review(n) for n in (1, 2)], None, None, None, None]
            return rpc([None, [None] * 10 + [node]])
        if url.startswith("https://www.google.com/maps?"):
            return Page("", cookies={"NID": "session"})
        return Page(self.place_page)


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> Google:
    answers = Google()

    class Fetcher:
        get = staticmethod(answers.get)

    monkeypatch.setattr(fetch, "AsyncFetcher", Fetcher)
    monkeypatch.setattr(fetch, "StealthyFetcher", None)
    return answers


async def test_it_offers_read_only_tools_that_reach_the_web(maps: str) -> None:
    """Read-only and open-world, so the app lets a first-party read skip asking."""
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(maps, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert sorted(tool.name for tool in tools) == ["reviews", "scrape"]
    for tool in tools:
        assert tool.annotations is not None
        assert (tool.annotations.read_only_hint, tool.annotations.open_world_hint) == (
            True,
            True,
        )


async def test_a_search_returns_its_places_with_a_summary_and_progress(
    maps: str, google: Google
) -> None:
    progress: list[float] = []

    result = await call(
        maps,
        "scrape",
        {"search_queries": ["coffee"], "location": "Austin", "max_places": 2},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["title"] for item in items] == ["Cafe 1", "Cafe 2"]
    assert items[0]["placeId"] == "ChIJplace1"
    assert result.content[0].text.startswith("2 Google Maps places")
    assert "Cafe 1 4.5 stars" in result.content[0].text
    assert progress[-1] == 2
    assert "q=coffee%20in%20Austin" in google.asked[0]


async def test_a_place_s_reviews_return_with_a_summary_and_progress(
    maps: str, google: Google
) -> None:
    progress: list[float] = []

    result = await call(
        maps, "reviews", {"place_ids": ["ChIJplace7"]}, LICENSE, progress
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["reviewId"] for item in items] == ["r1", "r2"]
    assert {item["title"] for item in items} == {"Cafe 7"}
    assert items[0]["inputPlaceId"] == "ChIJplace7"
    assert result.content[0].text.startswith("2 Google Maps reviews")
    assert progress[-1] == 2


async def test_a_sign_in_wall_reads_as_the_tool_s_error(
    maps: str, google: Google
) -> None:
    """Said as Google's refusal, as the scraper API said it."""
    google.place_page = "<html>Before you continue to Google</html>"

    result = await call(maps, "reviews", {"place_ids": ["ChIJplace7"]}, LICENSE)

    assert result.is_error
    assert "Google sign in required" in result.content[0].text


async def test_a_call_naming_nothing_to_scrape_is_refused(maps: str) -> None:
    result = await call(maps, "scrape", {}, LICENSE)

    assert result.is_error
    assert "search_queries" in result.content[0].text


async def test_a_url_that_is_not_http_is_refused(maps: str) -> None:
    result = await call(maps, "reviews", {"urls": ["maps/place/x"]}, LICENSE)

    assert result.is_error
    assert "Not an http(s) URL" in result.content[0].text


def test_without_a_license_the_plugin_answers_nothing(maps: str) -> None:
    refused = httpx2.post(maps, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})
