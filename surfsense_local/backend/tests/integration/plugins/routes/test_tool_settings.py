import pytest
from httpx import AsyncClient
from sqlalchemy import Engine

from modules.plugins.gateway.listing import list_tools
from shared.db import create_session_factory
from tests.integration.plugins.routes.conftest import add_notes

pytestmark = pytest.mark.integration


def offered(engine: Engine) -> list[str]:
    """What the gateway offers callers right now."""
    with create_session_factory(engine)() as session:
        return [t.qualified_name for t in list_tools(session)]


async def test_a_tool_switched_off_leaves_the_listing_and_the_gateway(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """The switch on the screen is the switch every caller obeys."""
    await add_notes(client, notes_url)
    await client.put("/plugins/third-party", json={"allowed": True})

    switched = await client.put(
        "/plugins/notes/tools/count", json={"enabled": False, "approval": "always"}
    )

    assert switched.status_code == 200, switched.text
    tools = {t["name"]: t for t in (await client.get("/plugins")).json()[0]["tools"]}
    assert tools["count"]["enabled"] is False
    assert tools["count"]["approval"] == "always"
    assert offered(engine) == ["notes__search"]


async def test_switching_a_tool_of_an_unknown_plugin_is_a_404(
    client: AsyncClient,
) -> None:
    """A stale screen gets a clear answer, not a silent success."""
    missing = await client.put("/plugins/nope/tools/x", json={"enabled": False})

    assert missing.status_code == 404


async def test_a_custom_plugin_is_held_while_third_party_plugins_are_off(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """A server added by URL is not reviewed by SurfSense, so the switch holds it like any other."""
    await add_notes(client, notes_url)
    assert offered(engine) == ["notes__search", "notes__count"]

    await client.put("/plugins/third-party", json={"allowed": False})
    assert offered(engine) == []

    await client.put("/plugins/third-party", json={"allowed": True})
    assert offered(engine) == ["notes__search", "notes__count"]


@pytest.mark.third_party_off
async def test_the_screen_reads_whether_third_party_plugins_are_allowed(
    client: AsyncClient,
) -> None:
    """Off until the user allows them, and the switch reads back what was set."""
    before = await client.get("/plugins/third-party")
    await client.put("/plugins/third-party", json={"allowed": True})
    after = await client.get("/plugins/third-party")

    assert before.json() == {"allowed": False}
    assert after.json() == {"allowed": True}
