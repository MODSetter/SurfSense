from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.models import InstalledPlugin, PluginKind, PluginSource
from modules.plugins.installed.recorded_tools import record_tools
from shared.db import create_session_factory


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """A session on the migrated database."""
    with create_session_factory(engine)() as opened:
        yield opened


class FakeSource:
    """A plugin's server listing from memory, so the gateway is tested on its own."""

    def __init__(self, tools: list[SourceTool]) -> None:
        self.tools = tools

    async def list_tools(self) -> list[SourceTool]:
        return self.tools


def tool(name: str, **annotations: bool) -> SourceTool:
    """A tool taking one required string, with the given annotations."""
    return SourceTool(
        name=name,
        title=None,
        description=f"The {name} tool.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        annotations=annotations,
    )


async def connect(
    session: Session,
    plugin_id: str,
    source: FakeSource,
    *,
    first_party: bool = True,
    url: str | None = None,
) -> InstalledPlugin:
    """A plugin connected the way Connect leaves it: its row and its first listing."""
    plugin = InstalledPlugin(
        id=plugin_id,
        kind=PluginKind.REMOTE,
        source=PluginSource.FIRST_PARTY if first_party else PluginSource.REGISTRY,
        # Loopback needs no consent; one server per plugin, as the database requires.
        url=url or f"http://127.0.0.1:9/{plugin_id}/mcp",
        entry={"name": plugin_id.title(), "hosts": []},
    )
    session.add(plugin)
    session.flush()
    record_tools(session, plugin, await source.list_tools())
    session.commit()
    return plugin
