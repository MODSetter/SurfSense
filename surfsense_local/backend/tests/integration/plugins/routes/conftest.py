from collections.abc import Iterator

import pytest
from httpx import AsyncClient

from tests.mcp_test_server import notes_server, serving


@pytest.fixture(autouse=True)
async def third_party_allowed(
    request: pytest.FixtureRequest, client: AsyncClient
) -> None:
    """Nearly every route here reaches a plugin's server, which waits for the switch, so
    each test starts as a user who allowed them; `third_party_off` keeps the default."""
    if request.node.get_closest_marker("third_party_off") is None:
        allowed = await client.put("/plugins/third-party", json={"allowed": True})
        assert allowed.status_code == 204


@pytest.fixture
def notes_url() -> Iterator[str]:
    """The notes plugin's server, live for the whole test."""
    with serving(notes_server().streamable_http_app()) as base:
        yield f"{base}/mcp"


async def add_notes(client: AsyncClient, url: str) -> None:
    """Connect the notes server by URL, as the screen does."""
    added = await client.post("/plugins/custom", json={"url": url, "name": "Notes"})
    assert added.status_code == 201, added.text
