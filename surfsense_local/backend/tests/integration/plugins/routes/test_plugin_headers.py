import pytest
from httpx import AsyncClient

from tests.mcp_test_server import RequiringHeader, notes_server, serving

pytestmark = pytest.mark.integration


def _keyed(name: str, value: str) -> RequiringHeader:
    return RequiringHeader(notes_server().streamable_http_app(), name, value)


async def _add(client: AsyncClient, url: str, headers: list[dict]) -> None:
    added = await client.post(
        "/plugins/custom", json={"url": url, "name": "Notes", "headers": headers}
    )
    assert added.status_code == 201, added.text


async def test_a_server_reading_its_key_from_another_header_connects(
    client: AsyncClient,
) -> None:
    """Exa-style `x-api-key`: the header reaches the server, and never comes back out."""
    with serving(_keyed("x-api-key", "k-secret-1")) as base:
        added = await client.post(
            "/plugins/custom",
            json={
                "url": f"{base}/mcp",
                "name": "Notes",
                "headers": [{"name": "x-api-key", "value": "k-secret-1"}],
            },
        )

    assert added.status_code == 201, added.text
    assert added.json()["auth_type"] == "headers"
    # Names, so Edit headers can show them; never a value.
    assert added.json()["header_names"] == ["x-api-key"]
    assert [t["name"] for t in added.json()["tools"]] == ["search", "count"]
    assert "k-secret-1" not in added.text
    assert "k-secret-1" not in (await client.get("/plugins")).text


async def test_every_header_given_reaches_the_server(client: AsyncClient) -> None:
    """A server wanting two headers, such as a key and a workspace, gets both."""
    app = RequiringHeader(_keyed("x-api-key", "k-1"), "x-workspace", "w-9")
    with serving(app) as base:
        await _add(
            client,
            f"{base}/mcp",
            [
                {"name": "x-api-key", "value": "k-1"},
                {"name": "X-Workspace", "value": "w-9"},
            ],
        )


@pytest.mark.parametrize(
    "header",
    [
        {"name": "Mcp-Session-Id", "value": "s-1"},
        {"name": "host", "value": "elsewhere.example"},
        {"name": "Cookie", "value": "a=b"},
        {"name": "bad name", "value": "v"},
        {"name": "x-api-key", "value": "line\r\nInjected: 1"},
        {"name": "x-api-key", "value": ""},
    ],
)
async def test_a_header_the_transport_owns_or_that_is_malformed_is_refused(
    client: AsyncClient, header: dict
) -> None:
    """Refused before anything is contacted, and nothing is stored."""
    refused = await client.post(
        "/plugins/custom",
        json={"url": "http://127.0.0.1:9/mcp", "name": "Notes", "headers": [header]},
    )

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_header_not_allowed"
    assert (await client.get("/plugins")).json() == []


async def test_the_same_header_twice_is_refused(client: AsyncClient) -> None:
    """Header names ignore case, so two spellings of one name are one header."""
    refused = await client.post(
        "/plugins/custom",
        json={
            "url": "http://127.0.0.1:9/mcp",
            "name": "Notes",
            "headers": [
                {"name": "x-api-key", "value": "a"},
                {"name": "X-API-Key", "value": "b"},
            ],
        },
    )

    assert refused.status_code == 422
    assert refused.json()["detail"]["code"] == "plugin_header_not_allowed"


async def test_new_headers_the_server_accepts_keep_the_tool_settings(
    client: AsyncClient,
) -> None:
    """Replacing a revoked key in place, as Replace key does for a Bearer key."""
    app = _keyed("x-api-key", "k-1")
    with serving(app) as base:
        await _add(client, f"{base}/mcp", [{"name": "x-api-key", "value": "k-1"}])
        await client.put("/plugins/notes/tools/count", json={"enabled": False})
        app.expected = b"k-2"

        replaced = await client.put(
            "/plugins/notes/headers",
            json={"headers": [{"name": "x-api-key", "value": "k-2"}]},
        )
        rechecked = await client.post("/plugins/notes/check")

    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["auth_type"] == "headers"
    assert "k-2" not in replaced.text
    tools = {t["name"]: t["enabled"] for t in replaced.json()["tools"]}
    assert tools == {"search": True, "count": False}
    assert rechecked.json()["check_failure"] is None


async def test_headers_the_server_refuses_are_not_saved(client: AsyncClient) -> None:
    """A mistyped key never replaces headers that work."""
    with serving(_keyed("x-api-key", "k-1")) as base:
        await _add(client, f"{base}/mcp", [{"name": "x-api-key", "value": "k-1"}])

        refused = await client.put(
            "/plugins/notes/headers",
            json={"headers": [{"name": "x-api-key", "value": "wrong"}]},
        )
        checked = await client.post("/plugins/notes/check")

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_needs_sign_in"
    assert checked.json()["check_failure"] is None


async def test_a_disconnected_plugin_with_headers_asks_for_them_again(
    client: AsyncClient,
) -> None:
    """Disconnecting drops the values; connecting again takes new ones."""
    with serving(_keyed("x-api-key", "k-1")) as base:
        await _add(client, f"{base}/mcp", [{"name": "x-api-key", "value": "k-1"}])
        await client.post("/plugins/notes/disconnect")

        bare = await client.post("/plugins/notes/connect")
        given = await client.put(
            "/plugins/notes/headers",
            json={"headers": [{"name": "x-api-key", "value": "k-1"}]},
        )

    assert bare.status_code == 422
    assert bare.json()["detail"]["code"] == "plugin_needs_key"
    assert given.status_code == 200, given.text
    assert given.json()["disconnected"] is False


async def test_headers_for_an_unknown_plugin_are_a_404(client: AsyncClient) -> None:
    """A stale screen gets a clear answer, not a silent success."""
    replaced = await client.put(
        "/plugins/nope/headers", json={"headers": [{"name": "x-k", "value": "v"}]}
    )

    assert replaced.status_code == 404
