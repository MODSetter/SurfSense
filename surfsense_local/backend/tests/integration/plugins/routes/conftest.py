from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from tests.mcp_test_server import notes_server, serving


@pytest.fixture
def notes_url() -> Iterator[str]:
    """The notes plugin's server, live for the whole test."""
    with serving(notes_server().streamable_http_app()) as base:
        yield f"{base}/mcp"


async def add_notes(client: AsyncClient, url: str) -> None:
    """Connect the notes server by URL, as the screen does."""
    added = await client.post("/plugins/custom", json={"url": url, "name": "Notes"})
    assert added.status_code == 201, added.text
