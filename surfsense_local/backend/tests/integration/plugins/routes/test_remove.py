import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, select

from modules.plugins.installed.models import InstalledPlugin, PluginTool
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


async def test_removing_deletes_the_plugin_its_key_and_its_tools(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """Nothing of a removed plugin is left to offer or to sign in with."""
    added = await client.post(
        "/plugins/custom", json={"url": notes_url, "name": "Notes", "token": "k-1"}
    )
    assert added.status_code == 201, added.text

    removed = await client.delete("/plugins/notes")

    assert removed.status_code == 204
    assert (await client.get("/plugins")).json() == []
    with create_session_factory(engine)() as session:
        assert session.scalars(select(InstalledPlugin)).all() == []
        assert session.scalars(select(PluginTool)).all() == []


async def test_removing_an_unknown_plugin_is_a_404(client: AsyncClient) -> None:
    """A stale screen gets a clear answer."""
    assert (await client.delete("/plugins/nope")).status_code == 404
