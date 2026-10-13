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


async def test_a_plugin_switched_off_keeps_its_choices_and_offers_nothing(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """Pausing a plugin is not disconnecting it: switched back on, it is as it was."""
    await add_notes(client, notes_url)
    await client.put("/plugins/third-party", json={"allowed": True})
    await client.put("/plugins/notes/tools/count", json={"approval": "always"})

    paused = await client.put("/plugins/notes", json={"enabled": False})

    assert paused.status_code == 200, paused.text
    assert paused.json()["enabled"] is False
    assert offered(engine) == []

    resumed = await client.put("/plugins/notes", json={"enabled": True})

    tools = {t["name"]: t for t in resumed.json()["tools"]}
    assert tools["count"]["approval"] == "always"
    assert offered(engine) == ["notes__search", "notes__count"]


async def test_switching_an_unknown_plugin_is_a_404(client: AsyncClient) -> None:
    """A stale screen gets a clear answer, not a silent success."""
    missing = await client.put("/plugins/nope", json={"enabled": False})

    assert missing.status_code == 404
