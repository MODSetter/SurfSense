"""Search in Add from the web: a SearXNG server's results as rows to add."""

import pytest
from httpx import AsyncClient
from starlette.responses import JSONResponse

from tests.integration.documents.web_sources.conftest import SearchServer
from tests.integration.documents.web_sources.stand_in_site import found, results

pytestmark = pytest.mark.integration


def search_url(workspace_id: int) -> str:
    """Where the dialog sends a search."""
    return f"/workspaces/{workspace_id}/documents/web/search"


async def test_a_search_shows_the_servers_results_as_rows_to_add(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """Each web link once, in the server's order, with the puller that would add it."""
    search_server.answer(
        results(
            found(
                "https://tides.example/explained", "Tide tables", "How  tides\nwork."
            ),
            found("https://youtu.be/dQw4w9WgXcQ", "Tides in a minute"),
            found("https://tides.example/explained", "Tide tables again"),
            found("ftp://tides.example/table.txt", "A file server"),
            found("http://[::1", "A broken link"),
            found("https://tides.example]/x", "A link with markdown left on it"),
            found("http:///tides", "A link with no host"),
            # Add would refuse these two, failing Add all's whole batch.
            found("https://tides.example/a b", "A link with a space in it"),
            found(f"https://tides.example/{'a' * 2078}", "A link too long to add"),
        )
    )

    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.status_code == 200, searched.text
    assert searched.json() == {
        "results": [
            {
                "url": "https://tides.example/explained",
                "title": "Tide tables",
                "description": "How tides work.",
                "site": "tides.example",
                "puller": "web_page",
            },
            {
                "url": "https://youtu.be/dQw4w9WgXcQ",
                "title": "Tides in a minute",
                "description": None,
                "site": "youtu.be",
                "puller": "youtube",
            },
        ],
        "more": True,
    }
    [asked] = search_server.asked
    assert dict(asked.query_params) == {
        "q": "tides",
        "format": "json",
        "pageno": "1",
        "categories": "general",
    }
    assert asked.headers["accept-language"] == "*"


async def test_show_more_asks_for_the_next_page_until_the_fifth(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """SearXNG counts pages from 1; the dialog shows at most five."""
    search_server.answer(results(found("https://tides.example/5", "Page five")))

    searched = await client.post(
        search_url(workspace_id), json={"query": "tides", "page": 4}
    )

    assert searched.json()["more"] is False
    assert search_server.asked[0].query_params["pageno"] == "5"


async def test_a_youtube_search_keeps_only_videos(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """Asked of the whole web for youtube.com; a channel is not a video to add."""
    search_server.answer(
        results(
            found("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Tides explained"),
            found("https://www.youtube.com/@seaschool", "Sea School"),
        )
    )

    searched = await client.post(
        search_url(workspace_id), json={"query": "tides", "source": "youtube"}
    )

    assert [row["url"] for row in searched.json()["results"]] == [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    ]
    assert search_server.asked[0].query_params["q"] == "tides site:youtube.com"


async def test_a_search_no_engine_answered_fails_rather_than_finding_nothing(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """An empty page from engines that all failed is no answer, not "no results"."""
    search_server.answer(results(unresponsive=[["duckduckgo", "timeout"]]))

    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.status_code == 502
    assert searched.json()["detail"] == {
        "code": "search_failed",
        "host": "127.0.0.1",
        "message": "the search server answered without searching",
    }


async def test_a_search_that_finds_nothing_says_so(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """Every engine answered, with nothing."""
    search_server.answer(results())

    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.json() == {"results": [], "more": False}


async def test_a_server_without_its_json_api_fails_the_search(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """A stock SearXNG answers 403 until `json` is in its search formats."""
    search_server.answer(JSONResponse({}, status_code=403))

    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.status_code == 502
    assert searched.json()["detail"]["code"] == "search_failed"


async def test_an_answer_without_a_results_list_fails_the_search(
    client: AsyncClient, workspace_id: int, search_server: SearchServer
) -> None:
    """SearXNG always lists its results, even none: a server that is not one has no search."""
    search_server.answer(JSONResponse({"error": "upstream failed"}))

    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.status_code == 502
    assert searched.json()["detail"]["code"] == "search_failed"


async def test_a_server_that_does_not_answer_is_unreachable(
    client: AsyncClient, workspace_id: int
) -> None:
    """Nothing listens on the discard port."""
    await client.put("/web-search/server", json={"url": "http://127.0.0.1:9"})

    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.status_code == 502
    assert searched.json()["detail"] == {
        "code": "search_unreachable",
        "host": "127.0.0.1",
        "message": "the search server could not be reached",
    }


async def test_surfsenses_server_is_asked_about_before_the_first_search(
    client: AsyncClient, workspace_id: int
) -> None:
    """No license, no plugin: the one question is the server's host, recorded off."""
    searched = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert searched.status_code == 403
    detail = searched.json()["detail"]
    assert detail["code"] == "egress_disabled"
    assert detail["hosts"] == ["searxng.surfsense.com"]
    assert detail["purpose"] == "web_search"
    listed = (await client.get("/egress")).json()
    row = next(r for r in listed if r["destination"] == "host:searxng.surfsense.com")
    assert row["enabled"] is False


async def test_an_empty_query_is_refused(
    client: AsyncClient, workspace_id: int
) -> None:
    """Nothing to send."""
    searched = await client.post(search_url(workspace_id), json={"query": "  "})

    assert searched.status_code == 422
