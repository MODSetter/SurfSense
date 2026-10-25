import pytest
from httpx import AsyncClient

from shared.config import get_plugin_host_settings
from tests.integration.documents.web_sources.conftest import ScraperHost
from tests.license_samples import INDIVIDUAL_KEY, import_license

pytestmark = pytest.mark.integration

TIDES = "https://tides.example/explained"
VIDEO = "https://www.youtube.com/watch?v=tide1"
CHANNEL = "https://www.youtube.com/@tides"


def results_page(organic: list[dict]) -> dict:
    """One Google results page, as the Google Search plugin answers it."""
    return {
        "searchQuery": {"term": "tides", "page": 1},
        "organicResults": organic,
        "paidResults": [{"title": "Buy tide clocks", "url": "https://ads.example"}],
        "peopleAlsoAsk": [{"question": "Why are there two tides?"}],
    }


def search_url(workspace_id: int) -> str:
    """Where the dialog sends a query."""
    return f"/workspaces/{workspace_id}/documents/web/search"


async def test_a_search_lists_google_s_pages_each_once_with_who_would_pull_it(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Ads and questions are left out; a repeated page is listed once."""
    organic = [
        {"title": "Tide tables explained", "url": TIDES, "description": "The moon."},
        {"title": "Tides in 3 minutes", "url": VIDEO, "description": ""},
        {"title": "Tide tables explained", "url": TIDES, "description": "The moon."},
        {"title": "The tides channel", "url": CHANNEL, "description": "Videos."},
    ]
    scraper_host.start({("google-search", "scrape"): lambda _: [results_page(organic)]})
    await import_license(client, "individual.lic")

    found = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert found.status_code == 200, found.text
    assert found.json() == {
        "link": None,
        "more": True,
        "failed": False,
        "results": [
            {
                "url": TIDES,
                "title": "Tide tables explained",
                "description": "The moon.",
                "site": "tides.example",
                "puller": "web_page",
                "fit": "one",
            },
            {
                "url": VIDEO,
                "title": "Tides in 3 minutes",
                "description": None,
                "site": "www.youtube.com",
                "puller": "youtube",
                "fit": "one",
            },
            {
                "url": CHANNEL,
                "title": "The tides channel",
                "description": "Videos.",
                "site": "www.youtube.com",
                "puller": "youtube",
                "fit": "list",
            },
        ],
    }
    assert scraper_host.calls == [
        ("google-search", "scrape", {"queries": ["tides"], "max_pages_per_query": 1})
    ]
    assert scraper_host.authorizations() == {f"License {INDIVIDUAL_KEY}"}


async def test_without_a_license_nothing_is_asked_or_sent(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The dialog shows the activation prompt instead."""
    scraper_host.start()

    found = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert found.status_code == 403
    assert found.json()["detail"]["code"] == "license_refused"
    assert found.json()["detail"]["reason"] == "missing_license"
    assert scraper_host.calls == []
    assert scraper_host.authorizations() == set()


async def test_a_license_the_plugin_host_refuses_comes_back_with_its_reason(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The host judges the license, never the app."""
    scraper_host.start()
    await import_license(client, "trial.lic")

    found = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert found.status_code == 403
    assert found.json()["detail"]["code"] == "license_refused"
    assert found.json()["detail"]["reason"] == "expired"


async def test_the_plugin_host_is_asked_about_before_anything_is_sent(
    client: AsyncClient, workspace_id: int
) -> None:
    """SurfSense's own host with no consent yet: one question, about the plugins."""
    await import_license(client, "individual.lic")

    found = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert found.status_code == 403
    assert found.json()["detail"]["code"] == "egress_disabled"
    assert found.json()["detail"]["host"] == "plugins.surfsense.com"
    assert found.json()["detail"]["purpose"] == "plugin"


async def test_a_plugin_host_that_cannot_be_reached_is_said_so(
    client: AsyncClient, workspace_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Told apart from a refused license, so the dialog says to try again later."""
    monkeypatch.setattr(
        get_plugin_host_settings(), "plugin_host_url", "http://127.0.0.1:9"
    )
    await import_license(client, "individual.lic")

    found = await client.post(search_url(workspace_id), json={"query": "tides"})

    assert found.status_code == 502
    assert found.json()["detail"]["code"] == "plugin_unavailable"
