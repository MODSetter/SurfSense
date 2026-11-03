"""A link's pull on the plugins queue, from the pending source the add route made."""

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, update

from modules.documents.models import Document, DocumentStatus
from modules.documents.web_sources.background_pull.pull_task import pull_web_source
from shared.queue import ingest_queue, plugins_queue
from tests.integration.documents.web_sources.conftest import Site, allow
from tests.integration.documents.web_sources.stand_in_site import PARAGRAPH, README
from tests.integration.documents.web_sources.stand_in_youtube import (
    CannedYouTube,
    Track,
    Video,
)
from worker.interrupted_documents import REASON as INTERRUPTED
from worker.interrupted_pulls import fail_interrupted_pulls

pytestmark = pytest.mark.integration

UNREADABLE = (
    "This page couldn't be read. Open it in your browser, save it as a PDF, "
    "and add the file instead."
)
VIDEO_ID = "dQw4w9WgXcQ"


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


async def test_a_pulled_page_becomes_its_main_text_under_its_title_and_is_indexed(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """Read as Chrome asks for it; the navigation and footer are left out."""
    url = stand_in_site.at("/explained")
    document_id = await added(client, workspace_id, url)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "pending"
    assert note["title"] == "Tide tables explained"
    assert PARAGRAPH in note["content"]
    assert "harbour office" not in note["content"]
    assert note["document_metadata"]["source_url"] == url
    assert note["document_metadata"]["fetched_at"]
    assert [(job.name, job.args) for job in ingest_queue.pending()] == [
        ("ingest_document", (document_id,))
    ]
    [asked] = stand_in_site.asked
    assert "Chrome" in asked.headers["user-agent"]


async def test_a_redirect_on_the_same_site_is_followed(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """The site's own answer, as a browser follows it."""
    document_id = await added(client, workspace_id, stand_in_site.at("/old-explained"))

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["title"] == "Tide tables explained"
    assert [request.url.path for request in stand_in_site.asked] == [
        "/old-explained",
        "/explained",
    ]


async def test_a_page_moved_to_a_host_not_allowed_fails_and_retry_asks_about_it(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """The new host is never contacted until the user allows it on Retry."""
    document_id = await added(client, workspace_id, stand_in_site.at("/elsewhere"))

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == (
        "This page moved to tides.example. Retry to allow reading it there."
    )
    assert note["document_metadata"]["moved_to"] == "tides.example"
    retry = f"/workspaces/{workspace_id}/documents/{document_id}/retry"
    asked = await client.post(retry)
    assert asked.status_code == 403
    assert asked.json()["detail"]["hosts"] == ["tides.example"]
    assert asked.json()["detail"]["purpose"] == "web_page"
    assert plugins_queue.pending() == []

    await allow(client, "tides.example")
    retried = await client.post(retry)

    assert retried.status_code == 200, retried.text
    assert [(job.name, job.args) for job in plugins_queue.pending()] == [
        ("pull_web_source", (document_id,))
    ]


@pytest.mark.parametrize(
    ("path", "sentence"),
    [
        ("/gone", "This page no longer exists at this link."),
        ("/wall", UNREADABLE),
        ("/empty", UNREADABLE),
        (
            "/table.pdf",
            "This link is a file, not a web page. Download it and add the file instead.",
        ),
    ],
)
async def test_a_link_that_is_no_readable_page_fails_and_says_why(
    client: AsyncClient,
    workspace_id: int,
    stand_in_site: Site,
    path: str,
    sentence: str,
) -> None:
    """The row keeps the link, so Retry can pull it again."""
    document_id = await added(client, workspace_id, stand_in_site.at(path))

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == sentence
    assert note["content"] is None
    assert ingest_queue.pending() == []


async def test_a_plain_text_file_is_kept_as_it_is(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """A README a server sends as text needs no extraction."""
    document_id = await added(client, workspace_id, stand_in_site.at("/README.md"))

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["title"] == "README.md"
    assert note["content"] == README.strip()


async def test_a_site_that_does_not_answer_fails_as_unreachable(
    client: AsyncClient, workspace_id: int
) -> None:
    """Nothing listens on the discard port."""
    document_id = await added(client, workspace_id, "http://127.0.0.1:9/tides")

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["error_message"] == (
        "This link couldn't be reached. Check your connection and retry."
    )


async def test_a_host_turned_off_since_the_click_is_not_asked_about_in_the_background(
    client: AsyncClient, workspace_id: int
) -> None:
    """The question is only ever asked on a click; a queued pull fails instead."""
    await allow(client, "tides.example")
    document_id = await added(client, workspace_id, "https://tides.example/explained")
    await client.put(
        "/egress", json={"destinations": ["host:tides.example"], "enabled": False}
    )

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == (
        "Sending to tides.example is off in Settings > Network."
    )


async def test_a_video_becomes_its_spoken_languages_transcript_with_its_facts(
    client: AsyncClient, workspace_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A person's French track before YouTube's own; never the English one, nor a translation."""
    youtube = CannedYouTube(
        monkeypatch,
        {
            VIDEO_ID: Video(
                title="Pourquoi les marées",
                channel="École de la mer",
                seconds=185,
                description="La lune et la mer.",
                tracks=(
                    Track("fr", "French (auto-generated)", True, ("la lune tire",)),
                    Track("en", "English", False, ("The moon pulls",)),
                    Track(
                        "fr-FR",
                        "French (France)",
                        False,
                        ("La lune tire", "La lune tire", "la mer &amp; les côtes"),
                    ),
                ),
            )
        },
    )
    await allow(client, "www.youtube.com")
    link = f"https://youtu.be/{VIDEO_ID}"
    document_id = await added(client, workspace_id, link)

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "pending", note["error_message"]
    assert note["title"] == "Pourquoi les marées"
    assert note["content"] == (
        "# Pourquoi les marées\n\n"
        "- **Channel:** École de la mer\n"
        "- **Duration:** 3:05\n"
        f"- **Link:** {link}\n"
        "- **Transcript:** French (France)\n\n"
        "## Description\n\nLa lune et la mer.\n\n"
        "## Transcript\n\nLa lune tire\nla mer & les côtes"
    )
    assert {url.split("?")[0] for url in youtube.asked} == {
        "https://www.youtube.com/watch",
        "https://www.youtube.com/youtubei/v1/player",
        "https://www.youtube.com/api/timedtext",
    }
    assert [url for url in youtube.asked if "/api/timedtext" in url] == [
        f"https://www.youtube.com/api/timedtext?v={VIDEO_ID}&lang=fr-FR"
    ]


async def test_a_video_without_captions_fails_and_says_so(
    client: AsyncClient, workspace_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """There is nothing of the video to keep without its words."""
    CannedYouTube(
        monkeypatch,
        {VIDEO_ID: Video("Silent tides", "Sea School", 60, "", tracks=())},
    )
    await allow(client, "www.youtube.com")
    document_id = await added(client, workspace_id, f"https://youtu.be/{VIDEO_ID}")

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "failed"
    assert note["error_message"] == (
        "This video has no captions, so there is no transcript to add."
    )


async def test_a_video_youtube_says_is_unavailable_fails_and_says_so(
    client: AsyncClient, workspace_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Private, removed or age-restricted read alike."""
    CannedYouTube(monkeypatch, {})
    await allow(client, "www.youtube.com")
    document_id = await added(client, workspace_id, f"https://youtu.be/{VIDEO_ID}")

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["error_message"] == (
        "This video can't be read: it may be private, removed or age-restricted."
    )


async def test_a_pull_of_a_retired_pullers_link_reads_it_as_a_page(
    client: AsyncClient,
    workspace_id: int,
    stand_in_site: Site,
    engine: Engine,
) -> None:
    """A note an earlier version added for its Reddit puller is pulled by its link now."""
    url = stand_in_site.at("/explained")
    document_id = await added(client, workspace_id, url)
    with engine.begin() as connection:
        connection.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(
                document_metadata={
                    "source_url": url,
                    "puller": "reddit",
                    "plugin_id": "reddit",
                }
            )
        )

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "pending"
    assert note["title"] == "Tide tables explained"


async def test_cancelling_a_queued_pull_drops_it(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """The page is never read."""
    document_id = await added(client, workspace_id, stand_in_site.at("/explained"))

    cancelled = await client.post(
        f"/workspaces/{workspace_id}/documents/{document_id}/cancel"
    )

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert all(plugins_queue.is_revoked(job) for job in plugins_queue.pending())


async def test_a_pull_that_ends_after_a_cancel_writes_nothing(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """The cancel stands: no text, no indexing."""
    document_id = await added(client, workspace_id, stand_in_site.at("/explained"))
    await client.post(f"/workspaces/{workspace_id}/documents/{document_id}/cancel")

    await pulled(document_id)

    note = await source(client, workspace_id, document_id)
    assert note["status"] == "cancelled"
    assert note["content"] is None
    assert ingest_queue.pending() == []
    assert stand_in_site.asked == []


async def test_retrying_a_failed_pull_pulls_the_link_again(
    client: AsyncClient, workspace_id: int, stand_in_site: Site
) -> None:
    """There is no text to index yet, so indexing alone would fail again."""
    document_id = await added(client, workspace_id, stand_in_site.at("/gone"))
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
    client: AsyncClient, workspace_id: int, stand_in_site: Site, engine: Engine
) -> None:
    """Huey dropped the running job with the worker; a queued one is left to run."""
    running = await added(client, workspace_id, stand_in_site.at("/explained"))
    queued = await added(client, workspace_id, stand_in_site.at("/old-explained"))
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
