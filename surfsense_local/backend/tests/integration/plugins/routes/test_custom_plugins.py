import pytest
from httpx import AsyncClient

from tests.mcp_test_server import (
    RecordingHeaders,
    RequiringToken,
    notes_server,
    serving,
)

pytestmark = pytest.mark.integration


async def test_a_server_added_by_url_is_connected_with_its_tools(
    client: AsyncClient,
) -> None:
    """Adding a remote server lists its tools once and keeps them with the plugin."""
    with serving(notes_server().streamable_http_app()) as base:
        added = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
    assert added.status_code == 201, added.text

    listed = (await client.get("/plugins")).json()

    assert [p["id"] for p in listed] == ["notes"]
    assert listed[0]["source"] == "custom"
    assert listed[0]["name"] == "Notes"
    assert [t["name"] for t in listed[0]["tools"]] == ["search", "count"]
    assert listed[0]["tools"][0]["enabled"] is True


async def test_a_token_reaches_the_server_and_never_comes_back_out(
    client: AsyncClient,
) -> None:
    """Credentials go to the plugin's server only: no response ever carries them."""
    app = RecordingHeaders(notes_server().streamable_http_app())
    with serving(app) as base:
        added = await client.post(
            "/plugins/custom",
            json={"url": f"{base}/mcp", "name": "Notes", "token": "k-secret-1"},
        )

    assert added.status_code == 201, added.text
    assert set(app.authorizations) == {"Bearer k-secret-1"}
    assert "k-secret-1" not in added.text
    assert "k-secret-1" not in (await client.get("/plugins")).text


async def test_a_server_that_needs_a_token_is_refused_until_one_is_given(
    client: AsyncClient,
) -> None:
    """The user is told what is missing, and nothing half-connected is left behind."""
    app = RequiringToken(notes_server().streamable_http_app(), "k-123")
    with serving(app) as base:
        refused = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
        accepted = await client.post(
            "/plugins/custom",
            json={"url": f"{base}/mcp", "name": "Notes", "token": "k-123"},
        )

    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "plugin_needs_sign_in"
    assert accepted.status_code == 201, accepted.text
    assert [p["id"] for p in (await client.get("/plugins")).json()] == ["notes"]


async def test_a_server_that_cannot_be_reached_is_refused_with_a_sentence(
    client: AsyncClient,
) -> None:
    """A wrong URL or a server that is down says so, and stores nothing."""
    refused = await client.post(
        "/plugins/custom", json={"url": "http://127.0.0.1:9/mcp", "name": "Gone"}
    )

    assert refused.status_code == 502
    assert refused.json()["detail"]["code"] == "plugin_unreachable"
    assert (await client.get("/plugins")).json() == []


async def test_a_host_not_yet_allowed_is_asked_about_before_anything_is_sent(
    client: AsyncClient,
) -> None:
    """One 403 names every host to allow, and Settings > Network lists them off."""
    refused = await client.post(
        "/plugins/custom",
        json={"url": "https://mcp.notes.example/mcp", "name": "Notes"},
    )

    assert refused.status_code == 403
    detail = refused.json()["detail"]
    assert detail["code"] == "egress_disabled"
    assert detail["hosts"] == ["mcp.notes.example"]
    assert detail["host"] == "mcp.notes.example"
    assert detail["purpose"] == "plugin"
    network = {
        row["host"]: row["enabled"] for row in (await client.get("/egress")).json()
    }
    assert network["mcp.notes.example"] is False
    assert (await client.get("/plugins")).json() == []


async def test_the_same_server_cannot_be_connected_twice(client: AsyncClient) -> None:
    """Two names for one server would split its tools and keys; the second is refused."""
    with serving(notes_server().streamable_http_app()) as base:
        first = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
        second = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "My notes"}
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert (detail["code"], detail["name"]) == ("plugin_already_connected", "Notes")
    assert [p["id"] for p in (await client.get("/plugins")).json()] == ["notes"]


async def test_a_second_plugin_cannot_take_a_name_in_use(client: AsyncClient) -> None:
    """Two plugins under one name would share an id, and opencode one server."""
    with serving(notes_server().streamable_http_app()) as first_base:
        await client.post(
            "/plugins/custom", json={"url": f"{first_base}/mcp", "name": "Notes"}
        )
    with serving(notes_server().streamable_http_app()) as second_base:
        second = await client.post(
            "/plugins/custom", json={"url": f"{second_base}/mcp", "name": "notes"}
        )

    assert second.status_code == 409
    detail = second.json()["detail"]
    assert (detail["code"], detail["name"]) == ("plugin_name_taken", "notes")


async def test_the_same_server_spelled_differently_is_still_the_same_server(
    client: AsyncClient,
) -> None:
    """Case in the scheme and a trailing slash do not make a second server."""
    with serving(notes_server().streamable_http_app()) as base:
        first = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "Notes"}
        )
        second = await client.post(
            "/plugins/custom",
            json={"url": f"{base.replace('http', 'HTTP')}/mcp/", "name": "Notes again"},
        )

    assert first.status_code == 201, first.text
    assert second.status_code == 409
    assert (await client.get("/plugins")).json()[0]["url"] == f"{base}/mcp"


async def test_a_plugin_named_surfsense_does_not_take_surfsenses_own_tools(
    client: AsyncClient,
) -> None:
    """The agent's own tools are a server named `surfsense`; a plugin is never given that name."""
    with serving(notes_server().streamable_http_app()) as base:
        added = await client.post(
            "/plugins/custom", json={"url": f"{base}/mcp", "name": "SurfSense"}
        )

    assert added.status_code == 201, added.text
    assert added.json()["id"] != "surfsense"
    assert added.json()["name"] == "SurfSense"


async def test_a_remote_server_must_use_https(client: AsyncClient) -> None:
    """The agent reaches remote plugins only through a TLS tunnel; a server on this computer may use HTTP."""
    added = await client.post(
        "/plugins/custom", json={"url": "http://notes.example.com/mcp", "name": "Notes"}
    )

    assert added.status_code == 422
    assert added.json()["detail"]["code"] == "plugin_needs_https"
