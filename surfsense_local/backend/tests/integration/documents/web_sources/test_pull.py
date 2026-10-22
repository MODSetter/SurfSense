"""A link's pull on the plugins queue, from the pending source the add route made."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, update

from modules.documents.models import Document, DocumentStatus
from modules.documents.web_sources.background_pull.pull_task import pull_web_source
from shared.config import get_plugin_host_settings
from shared.queue import ingest_queue, plugins_queue
from tests.integration.documents.web_sources.conftest import ScraperHost
from tests.integration.documents.web_sources.stand_in_plugins import refusing
from tests.license_samples import import_license
from worker.interrupted_documents import REASON as INTERRUPTED
from worker.interrupted_pulls import fail_interrupted_pulls

pytestmark = pytest.mark.integration

PAGE = "https://tides.example/explained"


def crawled(url: str, title: str, markdown: str) -> dict:
    """One page as Web Crawl answers it."""
    return {
        "url": url,
        "status": "success",
        "markdown": markdown,
        "metadata": {"source": url, "title": title},
        "error": None,
    }


async def added(client: AsyncClient, workspace_id: int, url: str) -> int:
    """The pending source the dialog's Add makes, its pull still queued."""
    response = await client.post(
        f"/workspaces/{workspace_id}/documents/web", json={"urls": [url]}
    )
    assert response.status_code == 201, response.text
    return response.json()["created"][0]["id"]


async def pulled(document_id: int) -> None:
    """The plugins worker runs the queued pull."""
    plugins_queue.flush()
    await asyncio.to_thread(pull_web_source.call_local, document_id)


async def source(client: AsyncClient, workspace_id: int, document_id: int) -> dict:
    """The source as the panel reads it."""
    return (
        await client.get(f"/workspaces/{workspace_id}/documents/{document_id}")
    ).json()


async def test_a_pulled_page_becomes_its_text_under_its_title_and_is_indexed(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Only this page is read: no link followed, the page kept whole."""
    scraper_host.start(
        {
            ("web-crawl", "crawl"): lambda _: [
                crawled(PAGE, "Tide tables explained", "# Tides\n\nThe moon pulls.")
            ]
        }
    )
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["title"] == "Tide tables explained"
    assert note["content"] == "# Tides\n\nThe moon pulls."
    assert note["status"] == "pending"
    assert note["document_metadata"]["source_url"] == PAGE
    assert note["document_metadata"]["fetched_at"]
    assert [(job.name, job.args) for job in ingest_queue.pending()] == [
        ("ingest_document", (document_id,))
    ]
    assert scraper_host.calls == [
        (
            "web-crawl",
            "crawl",
            {
                "start_urls": [PAGE],
                "max_crawl_depth": 0,
                "max_crawl_pages": 1,
                "max_length": 1_000_000,
                "max_links": 0,
            },
        )
    ]


async def test_a_page_that_cannot_be_read_fails_and_says_so(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The row keeps the link, so Retry can pull it again."""
    scraper_host.start({("web-crawl", "crawl"): refusing("No page could be read.")})
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == "This link couldn't be read."
    assert note["content"] is None
    assert ingest_queue.pending() == []


async def test_a_license_refused_when_the_pull_runs_says_so(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The host judges the license on the pull, not only on the click."""
    scraper_host.start()
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)
    await import_license(client, "trial.lic")

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == "Your SurfSense license has expired."


async def test_a_plugin_host_no_longer_allowed_is_not_asked_about_in_the_background(
    client: AsyncClient,
    workspace_id: int,
    scraper_host: ScraperHost,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The question is only ever asked on a click; a queued pull fails instead."""
    scraper_host.start()
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)
    monkeypatch.setattr(get_plugin_host_settings(), "plugin_host_url", None)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == (
        "Sending to plugins.surfsense.com is off in Settings > Network."
    )


async def test_cancelling_a_queued_pull_drops_it(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The plugin is never called for it."""
    scraper_host.start()
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)

    cancelled = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/cancel"
    )

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert all(plugins_queue.is_revoked(job) for job in plugins_queue.pending())


async def test_a_pull_that_ends_after_a_cancel_writes_nothing(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """The cancel stands: no text, no indexing."""
    scraper_host.start(
        {("web-crawl", "crawl"): lambda _: [crawled(PAGE, "Tides", "The moon.")]}
    )
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)
    await client.post(f"/workspaces/{workspace_id}/documents/{document_id}/cancel")

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "cancelled"
    assert note["content"] is None
    assert ingest_queue.pending() == []


async def test_retrying_a_failed_pull_pulls_the_link_again(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """There is no text to index yet, so indexing alone would fail again."""
    scraper_host.start({("web-crawl", "crawl"): refusing("No page could be read.")})
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, PAGE)
    await pulled(document_id)

    retried = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/retry"
    )

    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "pending"
    assert [(job.name, job.args) for job in plugins_queue.pending()] == [
        ("pull_web_source", (document_id,))
    ]
    assert ingest_queue.pending() == []


async def test_a_pull_the_app_closed_on_fails_when_the_plugins_worker_starts(
    client: AsyncClient,
    workspace_id: int,
    scraper_host: ScraperHost,
    engine: Engine,
) -> None:
    """Huey dropped the running job with the worker; a queued one is left to run."""
    scraper_host.start()
    await import_license(client, "individual.lic")
    running = await added(client, workspace_id, PAGE)
    queued = await added(client, workspace_id, "https://tides.example/table")
    with engine.begin() as connection:
        connection.execute(
            update(Document)
            .where(Document.id == running)
            .values(status=DocumentStatus.PROCESSING)
        )

    fail_interrupted_pulls()

    assert (await source(client, workspace_id, running))["status"] == "failed"
    assert (await source(client, workspace_id, running))["error_message"] == (
        INTERRUPTED
    )
    assert (await source(client, workspace_id, queued))["status"] == "pending"


async def test_a_video_whose_comments_cannot_be_read_is_kept_without_them(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Comments add to a source; the video itself is what was asked for."""
    video = "https://youtu.be/tide1"
    scraper_host.start(
        {
            ("youtube", "scrape"): lambda _: [
                {"title": "Why tides happen", "url": video, "text": "The moon."}
            ],
            ("youtube", "comments"): refusing("Comments are turned off."),
        }
    )
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, video)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "pending"
    assert note["title"] == "Why tides happen"
    assert "The moon." in note["content"]
    assert {(plugin, tool) for plugin, tool, _ in scraper_host.calls} == {
        ("youtube", "scrape"),
        ("youtube", "comments"),
    }


async def test_a_plugin_answer_the_puller_cannot_read_fails_the_source(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Never left processing: a price given as text, where an object was due."""
    product = "https://www.amazon.com/dp/B0TIDE0001"
    scraper_host.start(
        {
            ("amazon", "scrape"): lambda _: [
                {"title": "Tide Clock", "url": product, "price": "29.99"}
            ]
        }
    )
    await import_license(client, "individual.lic")
    document_id = await added(client, workspace_id, product)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == "This link couldn't be read."
    assert ingest_queue.pending() == []
