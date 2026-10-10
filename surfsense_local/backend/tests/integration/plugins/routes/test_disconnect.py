import pytest
from httpx import AsyncClient
from sqlalchemy import Engine, select

from modules.plugins.installed.models import InstalledPlugin, PluginTool
from modules.plugins.results.models import PluginCall, PluginCaller, PluginCallStatus
from modules.workspaces.models import Workspace
from shared.db import create_session_factory

pytestmark = pytest.mark.integration


async def test_disconnecting_removes_the_plugin_but_keeps_its_past_calls(
    client: AsyncClient, notes_url: str, engine: Engine
) -> None:
    """The plugin, its key and its tools go; what it answered stays in its threads."""
    added = await client.post(
        "/plugins/custom", json={"url": notes_url, "name": "Notes", "token": "k-1"}
    )
    assert added.status_code == 201, added.text
    with create_session_factory(engine)() as session:
        workspace = session.scalars(select(Workspace)).first() or Workspace(name="W")
        session.add(workspace)
        session.flush()
        session.add(
            PluginCall(
                workspace_id=workspace.id,
                caller=PluginCaller.AGENT,
                plugin_id="notes",
                tool="search",
                arguments={"query": "q"},
                status=PluginCallStatus.SUCCEEDED,
                result_text="found q",
            )
        )
        session.commit()

    removed = await client.delete("/plugins/notes")

    assert removed.status_code == 204
    assert (await client.get("/plugins")).json() == []
    with create_session_factory(engine)() as session:
        assert session.scalars(select(InstalledPlugin)).all() == []
        assert session.scalars(select(PluginTool)).all() == []
        assert [c.result_text for c in session.scalars(select(PluginCall))] == [
            "found q"
        ]


async def test_disconnecting_an_unknown_plugin_is_a_404(client: AsyncClient) -> None:
    """A stale screen gets a clear answer."""
    assert (await client.delete("/plugins/nope")).status_code == 404
