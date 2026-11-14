"""The agent's web tools as opencode's MCP client calls them: a search, a page, a video."""

from collections.abc import Iterator

import pytest
from starlette.requests import Request
from starlette.responses import Response

from modules.agent.tool_endpoint import script_page
from modules.agent.tool_endpoint.web_reach import REFUSED
from tests.integration.agent.tool_endpoint_client import ToolEndpoint
from tests.integration.documents.web_sources.stand_in_site import (
    PARAGRAPH,
    found,
    results,
    searxng,
    site,
)
from tests.integration.documents.web_sources.stand_in_youtube import (
    CannedYouTube,
    Track,
    Video,
)
from tests.mcp_test_server import serving

pytestmark = pytest.mark.integration

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.fixture
def stand_in_site() -> Iterator[str]:
    """A site on loopback, which needs no consent: its base address."""
    asked: list[Request] = []
    with serving(site(asked)) as base:
        yield base


async def allow(tools: ToolEndpoint, *hosts: str) -> None:
    """As the consent question's Allow does."""
    allowed = await tools.client.put(
        "/egress",
        json={"destinations": [f"host:{host}" for host in hosts], "enabled": True},
    )
    assert allowed.status_code == 200, allowed.text


async def listed_off(tools: ToolEndpoint, host: str) -> bool:
    """Settings > Network lists the host, switched off."""
    rows = (await tools.client.get("/egress")).json()
    return any(r["destination"] == f"host:{host}" and not r["enabled"] for r in rows)


async def test_it_offers_the_web_tools_after_its_own(tools: ToolEndpoint) -> None:
    """Last, so a local model's prompt cache of the others holds."""
    workspace_id = await tools.workspace()

    reply = await tools.request(workspace_id, "tools/list")

    listed = {tool["name"]: tool["inputSchema"] for tool in reply["result"]["tools"]}
    assert list(listed)[-3:] == [
        "search_web",
        "read_web_page",
        "read_youtube_transcript",
    ]
    assert listed["search_web"]["required"] == ["query"]
    assert listed["read_web_page"]["required"] == ["url"]
    assert listed["read_youtube_transcript"]["required"] == ["url"]


async def test_a_search_lists_each_result_with_its_link_and_snippet(
    tools: ToolEndpoint,
) -> None:
    """Through the SearXNG server Settings names, as the dialog searches."""
    answers = [
        results(
            found("https://tides.example/explained", "Tide tables", "How tides work.")
        )
    ]
    asked: list[Request] = []

    def answer(_: Request) -> Response:
        return answers.pop(0)

    workspace_id = await tools.workspace()
    with serving(searxng(answer, asked)) as server:
        await tools.client.put("/web-search/server", json={"url": server})
        text, is_error = await tools.call(
            workspace_id, "search_web", {"query": "tides"}
        )

    assert not is_error, text
    assert text == (
        "Page 1 of the results for 'tides':\n"
        "1. Tide tables\n   https://tides.example/explained\n"
        "   How tides work.\n"
        "Call surfsense_search_web again with page 2 for more."
    )
    assert asked[0].query_params["q"] == "tides"


async def test_a_search_server_not_allowed_is_refused_and_listed_to_allow(
    tools: ToolEndpoint,
) -> None:
    """A turn cannot ask: the step offers the question, Settings > Network lists the host."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(workspace_id, "search_web", {"query": "tides"})

    assert is_error
    assert text.startswith(f"{REFUSED}searxng.surfsense.com.\n")
    assert await listed_off(tools, "searxng.surfsense.com")


async def test_a_page_is_read_as_its_main_text_with_its_title_and_link(
    tools: ToolEndpoint, stand_in_site: str
) -> None:
    """Without the site's navigation and footer."""
    workspace_id = await tools.workspace()
    url = f"{stand_in_site}/explained"

    text, is_error = await tools.call(workspace_id, "read_web_page", {"url": url})

    assert not is_error, text
    assert text.startswith(f"Title: Tide tables explained\nLink: {url}\nLines 1-")
    assert PARAGRAPH in text
    assert "harbour office" not in text


async def test_a_long_page_comes_a_page_of_lines_at_a_time(
    tools: ToolEndpoint, stand_in_site: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each result names the offset to read on from."""
    monkeypatch.setattr(script_page, "PAGE_LINES", 1)
    workspace_id = await tools.workspace()
    url = f"{stand_in_site}/explained"

    first, _ = await tools.call(workspace_id, "read_web_page", {"url": url})
    last, is_error = await tools.call(
        workspace_id, "read_web_page", {"url": url, "offset": 3}
    )

    assert "\nLines 1-1 of 3. Call surfsense_read_web_page again with offset 2" in first
    assert PARAGRAPH not in first
    assert not is_error, last
    assert "\nLines 3-3 of 3.\n" in last
    assert PARAGRAPH in last


async def test_a_site_not_allowed_is_refused_before_it_is_contacted(
    tools: ToolEndpoint,
) -> None:
    """Named for the step to offer, and listed off in Settings > Network."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "read_web_page", {"url": "https://tides.example/explained"}
    )

    assert is_error
    assert text.startswith(f"{REFUSED}tides.example.\n")
    assert await listed_off(tools, "tides.example")


async def test_a_page_moved_to_a_site_not_allowed_names_that_site(
    tools: ToolEndpoint, stand_in_site: str
) -> None:
    """The site it moved to is never contacted."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "read_web_page", {"url": f"{stand_in_site}/elsewhere"}
    )

    assert is_error
    assert text.startswith(f"{REFUSED}tides.example.\n")


async def test_a_file_behind_a_link_is_not_read(
    tools: ToolEndpoint, stand_in_site: str
) -> None:
    """The agent is told what the user can do instead."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "read_web_page", {"url": f"{stand_in_site}/table.pdf"}
    )

    assert is_error
    assert text.startswith("This link is a file, not a web page.")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://example.com](https://example.com)",
        "https://[domain]/x",
    ],
)
async def test_only_web_addresses_are_read(tools: ToolEndpoint, url: str) -> None:
    """A file path, another scheme or a broken link never reaches the network."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(workspace_id, "read_web_page", {"url": url})

    assert is_error
    assert text == "url is a web address starting with https:// or http://."


async def test_a_video_is_read_as_its_spoken_transcript(
    tools: ToolEndpoint, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From www.youtube.com, once allowed, with its title and facts."""
    CannedYouTube(
        monkeypatch,
        {
            VIDEO_ID: Video(
                title="How tides work",
                channel="Sea School",
                seconds=65,
                description="The moon and the sea.",
                tracks=(
                    Track("en", "English (auto-generated)", True, ("the moon pulls",)),
                ),
            )
        },
    )
    workspace_id = await tools.workspace()
    await allow(tools, "www.youtube.com")
    url = f"https://youtu.be/{VIDEO_ID}"

    text, is_error = await tools.call(
        workspace_id, "read_youtube_transcript", {"url": url}
    )

    assert not is_error, text
    assert text.startswith(f"Title: How tides work\nLink: {url}\nLines 1-")
    assert "- **Channel:** Sea School" in text
    assert text.endswith("## Transcript\n\nthe moon pulls")


async def test_youtube_is_asked_about_before_a_transcript_is_read(
    tools: ToolEndpoint,
) -> None:
    """The one host a video is read from, whatever the link's."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id, "read_youtube_transcript", {"url": f"https://youtu.be/{VIDEO_ID}"}
    )

    assert is_error
    assert text.startswith(f"{REFUSED}www.youtube.com.\n")


async def test_a_link_that_is_no_video_is_sent_to_the_page_tool(
    tools: ToolEndpoint,
) -> None:
    """A channel, or another site."""
    workspace_id = await tools.workspace()

    text, is_error = await tools.call(
        workspace_id,
        "read_youtube_transcript",
        {"url": "https://www.youtube.com/@seaschool"},
    )

    assert is_error
    assert "surfsense_read_web_page" in text
