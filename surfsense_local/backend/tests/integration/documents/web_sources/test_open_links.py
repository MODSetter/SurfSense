"""Pasted links opened into rows to add: one row for a single thing, a list's items for a list."""

import pytest
from httpx import AsyncClient

from tests.integration.documents.web_sources.conftest import ScraperHost
from tests.integration.documents.web_sources.stand_in_plugins import refusing
from tests.license_samples import import_license

pytestmark = pytest.mark.integration

VIDEO = "https://youtu.be/tide1"
PAGE = "https://tides.example/explained"
CHANNEL = "https://www.youtube.com/@seaschool"
SHORT_TIKTOK = "https://vm.tiktok.com/ZM123/"
# How many videos the stand-in channel has.
CHANNEL_VIDEOS = 45


def channel_videos(arguments: dict) -> list[dict]:
    """The channel's newest videos first, as many as asked for."""
    count = min(arguments.get("max_results", 10), CHANNEL_VIDEOS)
    return [
        {
            "type": "video",
            "title": f"Tides, part {n}",
            "url": f"https://www.youtube.com/watch?v=tide{n}",
            "channelName": "Sea School",
            "duration": "00:03:00",
        }
        for n in range(1, count + 1)
    ]


def open_url(workspace_id: int) -> str:
    """Where the dialog sends what was pasted in its box."""
    return f"/workspaces/{workspace_id}/documents/web/open"


async def test_a_single_link_is_one_row_titled_by_itself_with_nothing_called(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Its real title comes with the pull: a preview would cost a plugin call."""
    scraper_host.start()

    opened = await client.post(
        open_url(workspace_id), json={"urls": [VIDEO, PAGE, SHORT_TIKTOK]}
    )

    assert opened.status_code == 200, opened.text
    assert opened.json() == {
        "groups": [
            {
                "link": None,
                "more": False,
                "failed": False,
                "results": [
                    {
                        "url": VIDEO,
                        "title": VIDEO,
                        "description": None,
                        "site": "youtu.be",
                        "puller": "youtube",
                        "fit": "one",
                    },
                    {
                        "url": PAGE,
                        "title": PAGE,
                        "description": None,
                        "site": "tides.example",
                        "puller": "web_page",
                        "fit": "one",
                    },
                    {
                        "url": SHORT_TIKTOK,
                        "title": SHORT_TIKTOK,
                        "description": None,
                        "site": "vm.tiktok.com",
                        "puller": "tiktok",
                        "fit": "short_link",
                    },
                ],
            }
        ]
    }
    assert scraper_host.calls == []


async def test_a_channel_opens_into_its_first_twenty_videos_with_more_to_show(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Each video is a row the user adds or leaves; nothing is added for them."""
    scraper_host.start({("youtube", "scrape"): channel_videos})
    await import_license(client, "individual.lic")

    opened = await client.post(open_url(workspace_id), json={"urls": [CHANNEL]})

    assert opened.status_code == 200, opened.text
    [group] = opened.json()["groups"]
    assert group["link"] == CHANNEL
    assert group["more"] is True
    assert group["failed"] is False
    assert len(group["results"]) == 20
    assert group["results"][0] == {
        "url": "https://www.youtube.com/watch?v=tide1",
        "title": "Tides, part 1",
        "description": "Sea School · 00:03:00",
        "site": "www.youtube.com",
        "puller": "youtube",
        "fit": "one",
    }
    assert scraper_host.calls == [
        ("youtube", "scrape", {"urls": [CHANNEL], "max_results": 20})
    ]
    assert (await client.get(f"/workspaces/{workspace_id}/documents")).json() == []


async def test_show_more_brings_the_next_twenty_until_the_list_ends(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The plugin takes a count, so each page asks for more and shows the rest."""
    scraper_host.start({("youtube", "scrape"): channel_videos})
    await import_license(client, "individual.lic")
    list_url = f"/workspaces/{workspace_id}/documents/web/list"

    second = await client.post(list_url, json={"url": CHANNEL, "page": 1})
    third = await client.post(list_url, json={"url": CHANNEL, "page": 2})

    assert second.status_code == 200, second.text
    assert [r["title"] for r in second.json()["results"]][:2] == [
        "Tides, part 21",
        "Tides, part 22",
    ]
    assert second.json()["more"] is True
    assert [r["title"] for r in third.json()["results"]] == [
        f"Tides, part {n}" for n in range(41, 46)
    ]
    assert third.json()["more"] is False


async def test_a_list_that_cannot_be_opened_says_so_and_the_rest_still_open(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """One dead channel does not cost the user the links pasted with it."""
    scraper_host.start({("youtube", "scrape"): refusing("Channel not found.")})
    await import_license(client, "individual.lic")

    opened = await client.post(open_url(workspace_id), json={"urls": [PAGE, CHANNEL]})

    assert opened.status_code == 200, opened.text
    single, channel = opened.json()["groups"]
    assert [r["url"] for r in single["results"]] == [PAGE]
    assert channel == {"link": CHANNEL, "more": False, "failed": True, "results": []}


async def test_opening_a_list_needs_a_license(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """A single link needs none to show; adding it is where the license is asked."""
    scraper_host.start({("youtube", "scrape"): channel_videos})

    opened = await client.post(open_url(workspace_id), json={"urls": [CHANNEL]})

    assert opened.status_code == 403
    assert opened.json()["detail"]["code"] == "license_refused"


async def test_a_license_the_host_refuses_on_a_list_comes_back_with_its_reason(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The dialog shows the license offer, as it does for a search."""
    scraper_host.start({("youtube", "scrape"): channel_videos})
    await import_license(client, "trial.lic")

    opened = await client.post(open_url(workspace_id), json={"urls": [CHANNEL]})
    more = await client.post(
        f"/workspaces/{workspace_id}/documents/web/list",
        json={"url": CHANNEL, "page": 1},
    )

    for answer in (opened, more):
        assert answer.status_code == 403, answer.text
        assert answer.json()["detail"]["code"] == "license_refused"
        assert answer.json()["detail"]["reason"] == "expired"
