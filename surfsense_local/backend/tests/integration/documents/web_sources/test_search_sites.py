"""A search on a site's own search, chosen beside the box, and Show more on any search."""

import pytest
from httpx import AsyncClient

from tests.integration.documents.web_sources.conftest import ScraperHost
from tests.license_samples import import_license

pytestmark = pytest.mark.integration

# How many videos the stand-in's YouTube search finds.
FOUND = 45


def youtube_found(arguments: dict) -> list[dict]:
    """YouTube's best matches first, as many as asked for."""
    count = min(arguments.get("max_results", 10), FOUND)
    return [
        {
            "type": "video",
            "title": f"Tides, result {n}",
            "url": f"https://www.youtube.com/watch?v=t{n}",
            "channelName": "Sea School",
        }
        for n in range(1, count + 1)
    ]


def google_pages(arguments: dict) -> list[dict]:
    """One results page per page asked, each with its own two links."""
    return [
        {
            "searchQuery": {"term": "tides", "page": page},
            "organicResults": [
                {
                    "title": f"Page {page} link {n}",
                    "url": f"https://p{page}.example/{n}",
                }
                for n in (1, 2)
            ],
        }
        for page in range(1, arguments.get("max_pages_per_query", 1) + 1)
    ]


def search_url(workspace_id: int) -> str:
    """Where the dialog sends a search, with the site chosen beside the box."""
    return f"/workspaces/{workspace_id}/documents/web/search"


async def test_a_search_on_youtube_runs_youtube_s_own_search(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Its first 20 videos, each a row to add, with more to show."""
    scraper_host.start({("youtube", "scrape"): youtube_found})
    await import_license(client, "individual.lic")

    found = await client.post(
        search_url(workspace_id), json={"query": "how tides work", "source": "youtube"}
    )

    assert found.status_code == 200, found.text
    group = found.json()
    assert (group["link"], group["more"], group["failed"]) == (None, True, False)
    assert len(group["results"]) == 20
    assert group["results"][0] == {
        "url": "https://www.youtube.com/watch?v=t1",
        "title": "Tides, result 1",
        "description": "Sea School",
        "site": "www.youtube.com",
        "puller": "youtube",
        "fit": "one",
    }
    assert scraper_host.calls == [
        (
            "youtube",
            "scrape",
            {"search_queries": ["how tides work"], "max_results": 20},
        )
    ]


async def test_show_more_on_a_site_search_brings_the_next_twenty(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """As on a list: the plugin takes a count, so page 3 reads 60 and shows the rest."""
    scraper_host.start({("youtube", "scrape"): youtube_found})
    await import_license(client, "individual.lic")

    third = await client.post(
        search_url(workspace_id),
        json={"query": "how tides work", "source": "youtube", "page": 2},
    )

    assert third.status_code == 200, third.text
    assert [r["title"] for r in third.json()["results"]] == [
        f"Tides, result {n}" for n in range(41, 46)
    ]
    assert third.json()["more"] is False


async def test_show_more_on_a_web_search_brings_google_s_next_page(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Google answers a page at a time; the next page is the one shown."""
    scraper_host.start({("google-search", "scrape"): google_pages})
    await import_license(client, "individual.lic")

    second = await client.post(
        search_url(workspace_id), json={"query": "tides", "page": 1}
    )

    assert second.status_code == 200, second.text
    assert [r["title"] for r in second.json()["results"]] == [
        "Page 2 link 1",
        "Page 2 link 2",
    ]
    assert scraper_host.calls == [
        ("google-search", "scrape", {"queries": ["tides"], "max_pages_per_query": 2})
    ]


@pytest.mark.parametrize("source", ["vimeo", "web_page"])
async def test_a_site_with_no_search_of_its_own_is_refused(
    client: AsyncClient, workspace_id: int, source: str
) -> None:
    """Web Crawl reads pages it is given; it searches nothing."""
    found = await client.post(
        search_url(workspace_id), json={"query": "tides", "source": source}
    )

    assert found.status_code == 422
