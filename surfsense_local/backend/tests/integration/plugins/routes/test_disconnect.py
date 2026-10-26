import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import InstalledPlugin
from shared.db import create_session_factory
from tests.integration.plugins.routes.conftest import add_notes
from tests.mcp_test_server import RequiringToken, notes_server, serving

pytestmark = pytest.mark.integration


async def _disconnected(client: AsyncClient, plugin_id: str = "notes") -> dict:
    disconnected = await client.post(f"/plugins/{plugin_id}/disconnect")
    assert disconnected.status_code == 200, disconnected.text
    return disconnected.json()


async def test_disconnecting_keeps_the_plugin_and_its_tool_settings_but_not_its_key(
    client: AsyncClient, engine: Engine
) -> None:
    """It stays in the user's list to connect again; only the sign-in goes."""
    with serving(RequiringToken(notes_server().streamable_http_app(), "k-1")) as base:
        added = await client.post(
            "/plugins/custom",
            json={"url": f"{base}/mcp", "name": "Notes", "token": "k-1"},
        )
        assert added.status_code == 201, added.text
        await client.put("/plugins/notes/tools/count", json={"enabled": False})

        plugin = await _disconnected(client)

    assert plugin["disconnected"] is True
    assert plugin["auth_type"] == "headers"
    assert {t["name"]: t["enabled"] for t in plugin["tools"]} == {
        "search": True,
        "count": False,
    }
    assert [p["id"] for p in (await client.get("/plugins")).json()] == ["notes"]
    with create_session_factory(engine)() as session:
        assert session.get_one(InstalledPlugin, "notes").credential_ciphertext is None


async def test_a_disconnected_plugins_tools_are_not_offered(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """The agent sees nothing of it until it is connected again."""
    await add_notes(client, notes_url)
    await client.put("/plugins/third-party", json={"allowed": True})

    await _disconnected(client)

    with create_session_factory(engine)() as session:
        assert list_tools(session) == []


async def test_connecting_a_keyless_plugin_again_lists_it_and_keeps_its_settings(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """Nothing to enter: the server is listed again and its tools offered."""
    await add_notes(client, notes_url)
    await client.put("/plugins/third-party", json={"allowed": True})
    await client.put("/plugins/notes/tools/count", json={"enabled": False})
    await _disconnected(client)

    connected = await client.post("/plugins/notes/connect")

    assert connected.status_code == 200, connected.text
    assert connected.json()["disconnected"] is False
    assert connected.json()["check_failure"] is None
    with create_session_factory(engine)() as session:
        assert [t.tool for t in list_tools(session)] == ["search"]


async def test_a_plugin_with_a_key_connects_again_with_a_new_key(
    client: AsyncClient,
) -> None:
    """Connect alone is refused: the key was dropped, so the screen asks for one."""
    with serving(RequiringToken(notes_server().streamable_http_app(), "k-1")) as base:
        await client.post(
            "/plugins/custom",
            json={"url": f"{base}/mcp", "name": "Notes", "token": "k-1"},
        )
        await _disconnected(client)

        refused = await client.post("/plugins/notes/connect")
        keyed = await client.put("/plugins/notes/key", json={"token": "k-1"})

    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "plugin_needs_key"
    assert keyed.status_code == 200, keyed.text
    assert keyed.json()["disconnected"] is False


async def test_a_disconnected_plugin_is_not_checked(
    client: AsyncClient, notes_url: str
) -> None:
    """With no sign-in, a check would only record a failure the user caused."""
    await add_notes(client, notes_url)
    await _disconnected(client)

    checked = await client.post("/plugins/notes/check")

    assert checked.status_code == 409, checked.text
    assert checked.json()["detail"]["code"] == "plugin_disconnected"


async def test_disconnecting_or_connecting_an_unknown_plugin_is_a_404(
    client: AsyncClient,
) -> None:
    """A stale screen gets a clear answer."""
    assert (await client.post("/plugins/nope/disconnect")).status_code == 404
    assert (await client.post("/plugins/nope/connect")).status_code == 404
