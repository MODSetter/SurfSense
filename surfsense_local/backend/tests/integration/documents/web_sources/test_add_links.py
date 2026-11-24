import pytest
from httpx import AsyncClient

from shared.queue import ingest_queue, plugins_queue
from tests.integration.documents.web_sources.conftest import allow

pytestmark = pytest.mark.integration

PAGE = "https://tides.example/explained"
VIDEO = "https://youtu.be/dQw4w9WgXcQ"
CHANNEL = "https://www.youtube.com/@tides"


def add_url(workspace_id: int) -> str:
    """Where the dialog sends the links a user picked or pasted."""
    return f"/workspaces/{workspace_id}/documents/web"


async def test_each_link_appears_at_once_as_a_pending_source_with_its_pull_queued(
    client: AsyncClient, workspace_id: int
) -> None:
    """No license: nothing is read while the user waits, and the dialog closes on the answer."""
    await allow(client, "tides.example", "www.youtube.com")

    added = await client.post(add_url(workspace_id), json={"urls": [PAGE, VIDEO]})

    assert added.status_code == 201, added.text
    created = added.json()["created"]
    assert [(d["title"], d["document_type"], d["status"]) for d in created] == [
        (PAGE, "NOTE", "pending"),
        (VIDEO, "NOTE", "pending"),
    ]
    assert added.json()["duplicates"] == []
    assert [(job.name, job.args) for job in plugins_queue.pending()] == [
        ("pull_web_source", (created[0]["id"],)),
        ("pull_web_source", (created[1]["id"],)),
    ]
    assert ingest_queue.pending() == []
    note = (
        await client.get(f"/workspaces/{workspace_id}/documents/{created[1]['id']}")
    ).json()
    assert note["content"] is None
    assert note["document_metadata"] == {"source_url": VIDEO, "puller": "youtube"}
    listed = (await client.get(f"/workspaces/{workspace_id}/documents")).json()
    assert {d["id"] for d in listed} == {d["id"] for d in created}


async def test_one_question_names_every_host_the_reads_start_on(
    client: AsyncClient, workspace_id: int
) -> None:
    """A page's own host, and YouTube's for a youtu.be link; nothing is written yet."""
    added = await client.post(
        add_url(workspace_id), json={"urls": [PAGE, VIDEO, CHANNEL]}
    )

    assert added.status_code == 403
    detail = added.json()["detail"]
    assert detail["code"] == "egress_disabled"
    assert detail["hosts"] == ["tides.example", "www.youtube.com"]
    assert detail["purpose"] == "web_page"
    assert (await client.get(f"/workspaces/{workspace_id}/documents")).json() == []
    assert plugins_queue.pending() == []


async def test_a_youtube_link_that_is_no_video_is_added_as_a_page(
    client: AsyncClient, workspace_id: int
) -> None:
    """A channel is read as the page it is, not refused."""
    await allow(client, "www.youtube.com")

    added = await client.post(add_url(workspace_id), json={"urls": [CHANNEL]})

    assert added.status_code == 201, added.text
    note = added.json()["created"][0]
    read = (
        await client.get(f"/workspaces/{workspace_id}/documents/{note['id']}")
    ).json()
    assert read["document_metadata"]["puller"] == "web_page"


async def test_a_link_already_in_sources_is_not_added_again(
    client: AsyncClient, workspace_id: int
) -> None:
    """Found by its link, wherever the user filed its source since, and not asked about."""
    await allow(client, "tides.example")
    first = await client.post(add_url(workspace_id), json={"urls": [PAGE]})
    await client.put(
        "/egress", json={"destinations": ["host:tides.example"], "enabled": False}
    )

    again = await client.post(add_url(workspace_id), json={"urls": [PAGE]})

    assert again.status_code == 201, again.text
    assert again.json()["created"] == []
    assert again.json()["duplicates"] == [
        {"url": PAGE, "document_id": first.json()["created"][0]["id"]}
    ]


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "http://a[b@example.com/", "http:///x.com"]
)
async def test_only_web_links_are_taken(
    client: AsyncClient, workspace_id: int, url: str
) -> None:
    """A file path, another scheme, or a link naming no host is never fetched."""
    added = await client.post(add_url(workspace_id), json={"urls": [url]})

    assert added.status_code == 422


async def test_a_broken_pasted_link_opens_no_row(
    client: AsyncClient, workspace_id: int
) -> None:
    """Refused as Add refuses it, not failed as a server error."""
    opened = await client.post(
        f"/workspaces/{workspace_id}/documents/web/open",
        json={"urls": [PAGE, "http://["]},
    )

    assert opened.status_code == 422


async def test_pasted_links_open_as_rows_without_reading_them(
    client: AsyncClient, workspace_id: int
) -> None:
    """A preview would cost as much as the pull, so each row is titled by its link."""
    opened = await client.post(
        f"/workspaces/{workspace_id}/documents/web/open",
        json={"urls": [PAGE, VIDEO, PAGE]},
    )

    assert opened.status_code == 200, opened.text
    assert opened.json() == {
        "results": [
            {
                "url": PAGE,
                "title": PAGE,
                "description": None,
                "site": "tides.example",
                "puller": "web_page",
            },
            {
                "url": VIDEO,
                "title": VIDEO,
                "description": None,
                "site": "youtu.be",
                "puller": "youtube",
            },
        ],
        "more": False,
    }
