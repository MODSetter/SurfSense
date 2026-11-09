"""The Web Crawl plugin as the app reaches it: its MCP server on the host, behind the license.

The web is faked at the static tier's fetch, `_fetch_static`, and DNS at the
destination guard's resolver: the guard refuses loopback, so a site served on
loopback could not be crawled. The host, the license check, the tool, the
extraction and the spider are real.
"""

from collections.abc import Iterator

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
from proprietary.web_crawl import connector, net_guard

LICENSE = {"Authorization": "License k-1"}

PARAGRAPH = "Sourdough needs a lively starter, a long rise and a hot oven. " * 12


def page(title: str, body: str) -> str:
    return (
        f"<html><head><title>{title}</title></head><body>"
        f"<article><h1>{title}</h1><p>{body}</p></article></body></html>"
    )


SITE = {
    "https://bread.example/": page(
        "Bread at home",
        PARAGRAPH
        + '<a href="/starter">Starter</a> <a href="/oven">Oven</a>'
        + ' <a href="https://elsewhere.example/">Elsewhere</a>',
    ),
    "https://bread.example/starter": page(
        "Keeping a starter", "Feed the starter twice a day. " * 20
    ),
    "https://bread.example/oven": page("Oven heat", "Preheat to 250 C. " * 30),
}


@pytest.fixture
def web_crawl(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """The real Web Crawl plugin on the host, its license checked by a stand-in Keygen."""
    with serving(StandInKeygen({"k-1": "VALID"}).app) as keygen_url:
        monkeypatch.setenv("KEYGEN_API_URL", accounts_url(keygen_url))
        monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
        with serving(host_app(plugins={"web-crawl"})) as base:
            yield f"{base}/web-crawl/mcp"


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """`SITE` answering the static tier, every name resolving public; keeps each URL fetched."""
    fetched: list[str] = []

    async def fetch_static(url: str) -> connector._Fetched:
        fetched.append(url)
        html = SITE.get(url)
        return connector._Fetched(200 if html else 404, url, html or "")

    async def no_browser(*_args, **_kwargs) -> None:
        raise NotImplementedError("no browser in tests")

    monkeypatch.setattr(connector, "_fetch_static", fetch_static)
    monkeypatch.setattr(
        connector.WebCrawlerConnector, "_crawl_with_dynamic", no_browser
    )
    monkeypatch.setattr(
        connector.WebCrawlerConnector, "_crawl_with_stealthy", no_browser
    )
    monkeypatch.setattr(net_guard, "_resolve_host", lambda _host: ["93.184.216.34"])
    return fetched


async def test_it_offers_one_read_only_tool_that_reaches_the_web(
    web_crawl: str,
) -> None:
    async with (
        httpx2.AsyncClient(headers=LICENSE) as http,
        Client(streamable_http_client(web_crawl, http_client=http)) as client,
    ):
        tools = (await client.list_tools()).tools

    assert [tool.name for tool in tools] == ["crawl"]
    assert tools[0].annotations is not None
    assert tools[0].annotations.read_only_hint is True
    assert tools[0].annotations.open_world_hint is True


async def test_one_page_is_read_with_its_text_in_the_summary(
    web_crawl: str, web: list[str]
) -> None:
    progress: list[float] = []

    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"]},
        LICENSE,
        progress,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert [item["url"] for item in items] == ["https://bread.example/"]
    assert items[0]["status"] == "success"
    assert "lively starter" in items[0]["markdown"]
    summary = result.content[0].text
    assert summary.splitlines()[0] == "1 page: 1 read"
    assert '"title":"Bread at home"' in summary
    assert '"url":"https://bread.example/"' in summary
    assert "lively starter" in summary
    # A first stage, then the page: rising, and whole at the end.
    assert progress == sorted(progress)
    assert progress[-1] == 1
    assert web == ["https://bread.example/"]


async def test_a_depth_one_crawl_follows_the_site_s_links_only(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"], "max_crawl_depth": 1},
        LICENSE,
    )

    assert not result.is_error
    items = result.structured_content["items"]
    assert {item["url"] for item in items} == set(SITE)
    followed = {item["url"]: item["crawl"] for item in items}
    assert followed["https://bread.example/oven"]["depth"] == 1
    assert (
        followed["https://bread.example/oven"]["referrerUrl"]
        == "https://bread.example/"
    )
    assert "https://elsewhere.example/" not in web
    text = result.content[0].text
    assert text.splitlines()[0] == "3 pages: 3 read"
    assert '"title":"Keeping a starter"' in text
    # Every page's text is in what the agent reads: opencode drops the
    # structured result when there is text, so a title alone was all it saw.
    assert "Feed the starter" in text
    assert "Preheat to 250 C" in text


async def test_max_length_cuts_each_page_s_text(web_crawl: str, web: list[str]) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"], "max_length": 40},
        LICENSE,
    )

    assert len(result.structured_content["items"][0]["markdown"]) == 40


async def test_a_loopback_address_is_refused_unfetched(
    web_crawl: str, web: list[str]
) -> None:
    """The host's own network is no page to read."""
    result = await call(
        web_crawl, "crawl", {"start_urls": ["http://127.0.0.1:8000/"]}, LICENSE
    )

    assert result.is_error
    assert "not publicly routable" in result.content[0].text
    assert web == []


async def test_a_url_that_is_not_http_is_refused(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl, "crawl", {"start_urls": ["file:///etc/passwd"]}, LICENSE
    )

    assert result.is_error
    assert "file:///etc/passwd" in result.content[0].text
    assert web == []


async def test_a_pattern_that_is_not_a_regex_is_refused(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {
            "start_urls": ["https://bread.example/"],
            "max_crawl_depth": 1,
            "include_url_patterns": ["(unclosed"],
        },
        LICENSE,
    )

    assert result.is_error
    assert "(unclosed" in result.content[0].text
    assert web == []


async def test_a_call_naming_nothing_to_read_is_refused(web_crawl: str) -> None:
    result = await call(web_crawl, "crawl", {"start_urls": []}, LICENSE)

    assert result.is_error


def test_without_a_license_the_plugin_answers_nothing(web_crawl: str) -> None:
    refused = httpx2.post(web_crawl, json={})

    assert (refused.status_code, refused.json()) == (401, {"reason": "missing_license"})


async def test_max_links_bounds_each_page_s_links(
    web_crawl: str, web: list[str]
) -> None:
    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/"], "max_links": 1},
        LICENSE,
    )

    item = result.structured_content["items"][0]
    assert [link["url"] for link in item["links"]] == ["https://bread.example/starter"]
    assert item["linksTotal"] == 3
    assert item["linksTruncated"] is True


async def test_a_missing_page_reads_as_an_http_error(
    web_crawl: str, web: list[str]
) -> None:
    """An HTTP error reads as one, not as an empty extraction."""
    result = await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/", "https://bread.example/gone"]},
        LICENSE,
    )

    items = {item["url"]: item for item in result.structured_content["items"]}
    gone = items["https://bread.example/gone"]
    assert gone["status"] == "failed"
    assert "Scrapling static: HTTP 404" in gone["error"]


@pytest.fixture
def server_module(monkeypatch: pytest.MonkeyPatch):
    """The plugin's server module; importing it reads the Keygen account."""
    monkeypatch.setenv("KEYGEN_ACCOUNT_ID", ACCOUNT)
    from proprietary.web_crawl import server

    return server


def _item(index: int, markdown: str) -> dict:
    return {
        "url": f"https://bread.example/{index}",
        "status": "success",
        "crawl": {
            "loadedUrl": f"https://bread.example/{index}",
            "depth": 1,
            "referrerUrl": "https://bread.example/",
        },
        "markdown": markdown,
        "metadata": {"title": f"Page {index}", "source": "x"},
        "contacts": {"emails": [f"e{i}@bread.example" for i in range(50)]},
        "links": [
            {"url": f"https://bread.example/l{i}", "text": "l"} for i in range(200)
        ],
        "linksTotal": 200,
        "error": None,
    }


def test_every_page_of_a_crawl_gets_its_share_of_the_text(server_module) -> None:
    """Ten long pages: the first no longer takes the whole cap from the other nine."""
    from mcp_server.results import MAX_TEXT_BYTES, tool_result

    server = server_module

    items = [_item(i, "é" * 50_000) for i in range(10)]

    result = tool_result(
        "10 pages: 10 read",
        items,
        project=server._projection(len(items)),
        clip_chars=MAX_TEXT_BYTES,
    )

    text = result.content[0].text
    assert len(text.encode("utf-8")) <= MAX_TEXT_BYTES
    for i in range(10):
        assert f'"url":"https://bread.example/{i}"' in text
    assert "more items not shown" not in text
    # Several pages: no link lists, contacts cut, the structured items whole.
    assert '"links"' not in text
    assert text.count("@bread.example") == 10 * server._AGENT_CONTACTS
    assert result.structured_content == {"items": items}


def _team_item(index: int) -> dict:
    """A lead-gen page: a whole team's contacts, and text full of quotes and lines."""
    item = _item(index, 'She said "hi".\n' * 4000)
    item["metadata"]["description"] = "Meet the people behind the bakery. " * 5
    item["contacts"] = {
        "emails": [f"first.last{i}@bakery-example.com" for i in range(12)],
        "phones": [f"+1 415 555 01{i:02d}" for i in range(12)],
        "socials": [
            f"https://www.linkedin.com/in/first-last-{i}-1234567" for i in range(12)
        ],
    }
    return item


@pytest.mark.parametrize("count", [2, 3, 10, 20])
def test_every_team_page_of_a_crawl_is_shown(server_module, count: int) -> None:
    """Escaped quotes and a team's contacts once pushed whole pages out of the reply."""
    from mcp_server.results import MAX_TEXT_BYTES, tool_result

    server = server_module
    items = [_team_item(i) for i in range(count)]

    result = tool_result(
        f"{count} pages: {count} read",
        items,
        project=server._projection(count),
        clip_chars=MAX_TEXT_BYTES,
    )

    text = result.content[0].text
    assert "more items not shown" not in text
    assert len(text.encode("utf-8")) <= MAX_TEXT_BYTES
    for i in range(count):
        assert f'"url":"https://bread.example/{i}"' in text
    # Each page keeps at least its floor of text, the reply most of the cap.
    assert text.count('She said \\"hi\\".') >= count * 15
    assert len(text.encode("utf-8")) > MAX_TEXT_BYTES * 0.9


def test_a_short_page_keeps_all_its_contacts(server_module) -> None:
    """Contacts are cut only when the page's text would not fit beside them."""
    from mcp_server.results import MAX_TEXT_BYTES, tool_result

    server = server_module
    items = [_team_item(i) for i in range(20)]
    for item in items:
        item["markdown"] = "Our team."

    text = (
        tool_result(
            "20 pages: 20 read",
            items,
            project=server._projection(20),
            clip_chars=MAX_TEXT_BYTES,
        )
        .content[0]
        .text
    )

    assert text.count("@bakery-example.com") == 20 * server._AGENT_CONTACTS


async def test_progress_ends_whole_when_a_start_url_is_given_twice(
    web_crawl: str, web: list[str]
) -> None:
    """The crawl reads a start URL given twice once: with a total of two, the
    last page's progress never reached it and was never sent."""
    progress: list[float] = []

    await call(
        web_crawl,
        "crawl",
        {"start_urls": ["https://bread.example/", "https://bread.example/#top"]},
        LICENSE,
        progress,
    )

    assert web == ["https://bread.example/"]
    assert progress[-1] == 1


def test_a_single_page_shows_its_first_links(server_module) -> None:
    from mcp_server.results import MAX_TEXT_BYTES, tool_result

    server = server_module

    result = tool_result(
        "1 page: 1 read",
        [_item(0, "short")],
        project=server._projection(1),
        clip_chars=MAX_TEXT_BYTES,
    )

    assert (
        result.content[0].text.count("https://bread.example/l") == server._AGENT_LINKS
    )


async def test_the_lifespan_warms_the_extractors_without_the_network(
    monkeypatch: pytest.MonkeyPatch, server_module
) -> None:
    server = server_module

    built: list[str] = []
    original = connector.WebCrawlerConnector._build_result

    def recording(self, raw_html, url, *args, **kwargs):
        result = original(self, raw_html, url, *args, **kwargs)
        built.append(result["metadata"].get("date"))
        return result

    async def no_fetch(*_a, **_k):
        raise AssertionError("the warm-up must not fetch")

    monkeypatch.setattr(connector.WebCrawlerConnector, "_build_result", recording)
    monkeypatch.setattr(connector, "_fetch_static", no_fetch)

    async with server.lifespan():
        pass

    assert built == ["2024-05-01", None]
