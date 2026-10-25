import pytest
from httpx import AsyncClient

from shared.queue import ingest_queue, plugins_queue
from tests.integration.documents.web_sources.conftest import ScraperHost
from tests.license_samples import import_license

pytestmark = pytest.mark.integration

PAGE = "https://tides.example/explained"
VIDEO = "https://youtu.be/tide1"
CHANNEL = "https://www.youtube.com/@tides"
SHORT_TIKTOK = "https://vm.tiktok.com/ZM123/"


def add_url(workspace_id: int) -> str:
    """Where the dialog sends the links a user picked or pasted."""
    return f"/workspaces/{workspace_id}/documents/web"


async def test_each_link_appears_at_once_as_a_pending_source_with_its_pull_queued(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Nothing is pulled while the user waits: the dialog closes on the answer."""
    scraper_host.start()
    await import_license(client, "individual.lic")

    added = await client.post(add_url(workspace_id), json={"urls": [PAGE, VIDEO]})

    assert added.status_code == 201, added.text
    created = added.json()["created"]
    assert [(d["title"], d["document_type"], d["status"]) for d in created] == [
        (PAGE, "NOTE", "pending"),
        (VIDEO, "NOTE", "pending"),
    ]
    assert added.json()["duplicates"] == []
    assert added.json()["rejected"] == []
    assert [(job.name, job.args) for job in plugins_queue.pending()] == [
        ("pull_web_source", (created[0]["id"],)),
        ("pull_web_source", (created[1]["id"],)),
    ]
    assert ingest_queue.pending() == []
    assert scraper_host.calls == []
    note = (
        await client.get(f"/workspaces/{workspace_id}/documents/{created[1]['id']}")
    ).json()
    assert note["content"] is None
    assert note["document_metadata"]["source_url"] == VIDEO
    assert note["document_metadata"]["puller"] == "youtube"
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert {d["id"] for d in listed} == {d["id"] for d in created}


async def test_a_link_that_is_not_one_thing_is_refused_with_why(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """A channel is many videos; a TikTok short link points at a host not allowed."""
    scraper_host.start()
    await import_license(client, "individual.lic")

    added = await client.post(
        add_url(workspace_id), json={"urls": [CHANNEL, SHORT_TIKTOK, PAGE]}
    )

    assert added.status_code == 201, added.text
    assert [d["title"] for d in added.json()["created"]] == [PAGE]
    assert added.json()["rejected"] == [
        {"url": CHANNEL, "reason": "list"},
        {"url": SHORT_TIKTOK, "reason": "short_link"},
    ]


async def test_a_link_already_in_sources_is_not_added_again(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Found by its link, wherever the user filed its source since."""
    scraper_host.start()
    await import_license(client, "individual.lic")
    first = await client.post(add_url(workspace_id), json={"urls": [PAGE]})

    again = await client.post(add_url(workspace_id), json={"urls": [PAGE, VIDEO]})

    assert again.status_code == 201, again.text
    assert [d["title"] for d in again.json()["created"]] == [VIDEO]
    assert again.json()["duplicates"] == [
        {"url": PAGE, "document_id": first.json()["created"][0]["id"]}
    ]


async def test_without_a_license_no_source_is_made(
    client: AsyncClient, workspace_id: int, scraper_host: ScraperHost
) -> None:
    """Refused before anything is written, asked or sent."""
    scraper_host.start()

    added = await client.post(add_url(workspace_id), json={"urls": [PAGE]})

    assert added.status_code == 403
    assert added.json()["detail"]["code"] == "license_refused"
    assert (await client.get(f"/workspaces/{workspace_id}/documents")).json() == []
    assert plugins_queue.pending() == []


async def test_without_consent_for_the_plugin_host_no_source_is_made(
    client: AsyncClient, workspace_id: int
) -> None:
    """The app's prompt asks, then sends the same request again."""
    await import_license(client, "individual.lic")

    added = await client.post(add_url(workspace_id), json={"urls": [PAGE]})

    assert added.status_code == 403
    assert added.json()["detail"]["code"] == "egress_disabled"
    assert (await client.get(f"/workspaces/{workspace_id}/documents")).json() == []


async def test_only_web_links_are_taken(client: AsyncClient, workspace_id: int) -> None:
    """A file path or another scheme never reaches a plugin."""
    added = await client.post(
        add_url(workspace_id), json={"urls": ["file:///etc/passwd"]}
    )

    assert added.status_code == 422
