import pytest
from httpx import AsyncClient

from tests.mcp_test_server import RequiringToken, notes_server, serving

pytestmark = pytest.mark.integration


async def _connect_with_key(client: AsyncClient, url: str, key: str) -> None:
    added = await client.post(
        "/plugins/custom", json={"url": url, "name": "Notes", "token": key}
    )
    assert added.status_code == 201, added.text


async def test_a_new_key_the_server_accepts_keeps_the_tool_settings(
    client: AsyncClient,
) -> None:
    """Replacing a revoked key clears the sign-in, and the user's choices per tool stay."""
    app = RequiringToken(notes_server().streamable_http_app(), "k-1")
    with serving(app) as base:
        await _connect_with_key(client, f"{base}/mcp", "k-1")
        await client.put("/plugins/notes/tools/count", json={"enabled": False})
        app.expected = b"Bearer k-2"
        await client.post("/plugins/notes/check")

        replaced = await client.put("/plugins/notes/key", json={"token": "k-2"})
        rechecked = await client.post("/plugins/notes/check")

    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["check_failure"] is None
    tools = {t["name"]: t["enabled"] for t in replaced.json()["tools"]}
    assert tools == {"search": True, "count": False}
    assert rechecked.json()["check_failure"] is None


async def test_a_key_the_server_refuses_is_not_saved(client: AsyncClient) -> None:
    """A mistyped key never replaces one that works."""
    app = RequiringToken(notes_server().streamable_http_app(), "k-1")
    with serving(app) as base:
        await _connect_with_key(client, f"{base}/mcp", "k-1")

        refused = await client.put("/plugins/notes/key", json={"token": "wrong"})
        checked = await client.post("/plugins/notes/check")

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_needs_sign_in"
    assert checked.json()["check_failure"] is None


async def test_replacing_the_key_of_an_unknown_plugin_is_a_404(
    client: AsyncClient,
) -> None:
    """A stale screen gets a clear answer, not a silent success."""
    replaced = await client.put("/plugins/nope/key", json={"token": "k"})

    assert replaced.status_code == 404
