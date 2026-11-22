"""While third-party plugins are off, SurfSense contacts no third-party plugin's server."""

import pytest
from httpx import AsyncClient

from tests.mcp_test_server import RecordingHeaders, notes_server, serving

pytestmark = pytest.mark.integration


async def _switch(client: AsyncClient, allowed: bool) -> None:
    switched = await client.put("/plugins/third-party", json={"allowed": allowed})
    assert switched.status_code == 204


def _refused_as_off(answer) -> None:
    assert answer.status_code == 403, answer.text
    assert answer.json()["detail"]["code"] == "third_party_off"


@pytest.mark.third_party_off
async def test_no_server_is_added_by_url_while_third_party_plugins_are_off(
    client: AsyncClient,
) -> None:
    """Adding lists the server's tools, so it waits for the switch, sending nothing."""
    app = RecordingHeaders(notes_server().streamable_http_app())
    with serving(app) as base:
        added = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )

    _refused_as_off(added)
    assert app.authorizations == []
    assert (await client.get("/plugins")).json() == []


async def test_nothing_reaches_a_saved_third_party_plugin_while_they_are_off(
    client: AsyncClient,
) -> None:
    """Refresh tools, a new key or headers, connecting and signing in each wait for the switch."""
    app = RecordingHeaders(notes_server().streamable_http_app())
    with serving(app) as base:
        await _switch(client, True)
        added = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
        assert added.status_code == 201, added.text
        await client.post("/plugins/notes/disconnect")
        await _switch(client, False)
        sent_before = len(app.authorizations)

        answers = [
            await client.post("/plugins/notes/check"),
            await client.put("/plugins/notes/key", json={"token": "k-1"}),
            await client.put(
                "/plugins/notes/headers",
                json={"headers": [{"name": "x-api-key", "value": "k-1"}]},
            ),
            await client.post("/plugins/notes/connect"),
            await client.post("/plugins/notes/sign-in"),
        ]

    for answer in answers:
        _refused_as_off(answer)
    assert len(app.authorizations) == sent_before


async def test_a_third_party_plugin_is_still_removed_while_they_are_off(
    client: AsyncClient,
) -> None:
    """Removing touches only this computer, so the switch does not hold it."""
    with serving(notes_server().streamable_http_app()) as base:
        await _switch(client, True)
        await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
    await _switch(client, False)

    removed = await client.delete("/plugins/notes")

    assert removed.status_code == 204
    assert (await client.get("/plugins")).json() == []
