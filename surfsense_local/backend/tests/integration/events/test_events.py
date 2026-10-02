"""The freshness push end to end: an /internal/events POST reaches a subscriber.

Run against a real uvicorn server over TCP, not the in-process ASGI transport:
that transport awaits the app to completion before returning a response, so it
can never read an endless SSE stream incrementally (it would hang). A real socket
is also closer to what the renderer's EventSource actually does.
"""

import json
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def _line_starting(lines: AsyncIterator[str], prefix: str) -> str:
    async for line in lines:
        if line.startswith(prefix):
            return line
    raise AssertionError(f"stream ended before a line starting {prefix!r}")


async def test_an_internal_event_reaches_a_subscriber(base_url: str) -> None:
    """A worker notice arrives on the workspace's stream as a named SSE frame."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id = (await client.post("/workspaces", json={"name": "w"})).json()[
            "id"
        ]

        async with client.stream("GET", f"/workspaces/{workspace_id}/events") as reply:
            assert reply.status_code == 200
            assert reply.headers["content-type"].startswith("text/event-stream")
            lines = reply.aiter_lines()

            # Wait until subscribed, so the POST below cannot race ahead of us.
            await _line_starting(lines, ": connected")

            posted = await client.post(
                "/internal/events",
                json={
                    "workspace_id": workspace_id,
                    "kind": "documents",
                    "ids": [7],
                    "status": "ready",
                },
            )
            assert posted.status_code == 202

            assert await _line_starting(lines, "event:") == "event: documents"
            data = await _line_starting(lines, "data:")
            assert json.loads(data.removeprefix("data: ")) == {
                "ids": [7],
                "status": "ready",
            }


async def test_an_unknown_workspace_stream_is_a_404(base_url: str) -> None:
    """The stream validates the workspace like every other workspace-scoped route."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        assert (await client.get("/workspaces/9999/events")).status_code == 404


async def _event_after(client: AsyncClient, workspace_id: int, change) -> tuple:
    """The first event a subscriber gets once `change` has run."""
    async with client.stream("GET", f"/workspaces/{workspace_id}/events") as reply:
        lines = reply.aiter_lines()
        await _line_starting(lines, ": connected")
        await change()
        name = (await _line_starting(lines, "event:")).removeprefix("event: ")
        data = await _line_starting(lines, "data:")
        return name, json.loads(data.removeprefix("data: "))


async def _workspace_with_a_note(client: AsyncClient) -> tuple[int, int]:
    """A workspace holding one note, written before anyone subscribes."""
    workspace_id = (await client.post("/workspaces", json={"name": "w"})).json()["id"]
    note = await client.post(
        f"/workspaces/{workspace_id}/documents", json={"title": "Note", "content": "x"}
    )
    return workspace_id, note.json()["id"]


async def test_a_note_written_through_the_api_reaches_a_subscriber(
    base_url: str,
) -> None:
    """A plugin's note shows in an open window at once, as an upload there does."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id = (await client.post("/workspaces", json={"name": "w"})).json()[
            "id"
        ]
        written: dict = {}

        async def write() -> None:
            written.update(
                (
                    await client.post(
                        f"/workspaces/{workspace_id}/documents",
                        json={"title": "Note", "content": "x"},
                    )
                ).json()
            )

        event = await _event_after(client, workspace_id, write)

        assert event == ("documents", {"ids": [written["id"]], "status": "pending"})


async def test_each_uploaded_file_reaches_a_subscriber(base_url: str) -> None:
    """A second window learns of every file uploaded in the first."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id = (await client.post("/workspaces", json={"name": "w"})).json()[
            "id"
        ]

        async with client.stream("GET", f"/workspaces/{workspace_id}/events") as reply:
            lines = reply.aiter_lines()
            await _line_starting(lines, ": connected")
            uploaded = await client.post(
                f"/workspaces/{workspace_id}/documents/upload",
                files=[
                    ("files", ("first.txt", b"one", "text/plain")),
                    ("files", ("second.txt", b"two", "text/plain")),
                ],
            )
            events = [
                json.loads(
                    (await _line_starting(lines, "data:")).removeprefix("data: ")
                )
                for _ in range(2)
            ]

        assert events == [
            {"ids": [document["id"]], "status": "pending"}
            for document in uploaded.json()["created"]
        ]


async def test_a_renamed_document_reaches_a_subscriber(base_url: str) -> None:
    """A rename runs no ingest, so no worker would ever notify of it."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id, note_id = await _workspace_with_a_note(client)

        async def rename() -> None:
            await client.patch(
                f"/workspaces/{workspace_id}/documents/{note_id}",
                json={"title": "Renamed"},
            )

        event = await _event_after(client, workspace_id, rename)

        assert event == ("documents", {"ids": [note_id], "status": "pending"})


async def test_a_cancelled_and_a_retried_ingest_reach_a_subscriber(
    base_url: str,
) -> None:
    """Both are the API's own changes of status, which no worker notifies of."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id, note_id = await _workspace_with_a_note(client)
        document = f"/workspaces/{workspace_id}/documents/{note_id}"

        async def cancel() -> None:
            await client.post(f"{document}/cancel")

        async def retry() -> None:
            await client.post(f"{document}/retry")

        cancelled = await _event_after(client, workspace_id, cancel)
        retried = await _event_after(client, workspace_id, retry)

        assert cancelled == ("documents", {"ids": [note_id], "status": "cancelled"})
        assert retried == ("documents", {"ids": [note_id], "status": "pending"})


async def test_a_deleted_document_reaches_a_subscriber(base_url: str) -> None:
    """The window drops a source another client removed."""
    async with AsyncClient(base_url=base_url, timeout=5) as client:
        workspace_id, note_id = await _workspace_with_a_note(client)

        async def remove() -> None:
            await client.delete(f"/workspaces/{workspace_id}/documents/{note_id}")

        event = await _event_after(client, workspace_id, remove)

        assert event == ("documents", {"ids": [note_id], "status": "deleted"})
